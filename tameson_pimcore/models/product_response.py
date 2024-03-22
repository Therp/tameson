###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

import codecs
import logging
from datetime import datetime

import requests
from dateutil.relativedelta import relativedelta
from psycopg2.errors import UniqueViolation

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
CURRENCY_DICT = {"USD": 3, "EUR": 1, "GBP": 150}  # currency ids in Odoo DB


def create_or_find_categ(env, path, model="product.category", start=3, end=-1):
    child_categ = env[model]
    final_categ = env[model]
    if path:
        if end == 0:
            end = len(path.split("/"))
        categ_path = path.split("/")[start:end]
        categ_path_len = len(categ_path)
        for pos, categ in enumerate(categ_path[::-1]):
            this_path = " / ".join(categ_path[: categ_path_len - pos])
            break_loop = False
            this_categ = child_categ.search(
                [("complete_name", "=", this_path)], limit=1
            )
            if not this_categ:
                this_categ = child_categ.create({"name": categ})
            else:
                break_loop = True
            if child_categ:
                child_categ.parent_id = this_categ
            child_categ = this_categ
            if not final_categ:
                final_categ = this_categ
            if break_loop:
                break
    return final_categ


def add_translation(env, product, lang_code, src, value):
    nl_name = env["ir.translation"].search(
        [
            ("res_id", "=", product.id),
            ("name", "=", "product.template,name"),
            ("lang", "=", lang_code),
        ]
    )
    if not nl_name:
        nl_name = env["ir.translation"].create(
            {
                "type": "model",
                "name": "product.template,name",
                "lang": lang_code,
                "res_id": product.id,
                "src": src,
                "value": value,
                "state": "translated",
            }
        )
    else:
        nl_name.write({"value": value})


class PimcoreProductResponse(models.Model):
    _name = "pimcore.product.response"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "PimcoreProductResponse"
    _rec_name = "name"
    _order = "name DESC"

    name = fields.Char(default="New")
    type = fields.Selection(selection=[("full", "Full"), ("new", "New")])
    line_ids = fields.One2many(
        comodel_name="pimcore.product.response.line",
        inverse_name="response_id",
    )
    config_id = fields.Many2one(
        comodel_name="pimcore.config",
        ondelete="cascade",
    )

    def create(self, vals):
        if vals.get("name", "New") == "New":
            vals["name"] = self.env["ir.sequence"].next_by_code("pimcore.response")
        return super(PimcoreProductResponse, self).create(vals)

    def import_product_data(self, chunk_size=10):
        self.env.cr.execute(
            "delete from pimcore_product_response_line where draft = true"
        )
        self.env.cr.execute(
            """DELETE FROM pimcore_product_response_line
WHERE id NOT IN
(
    SELECT MAX(id) AS id
    FROM pimcore_product_response_line
    WHERE state = 'draft'
    GROUP BY sku
) and state = 'draft';
SELECT rl.id,
pt.id,
rl.modification_date,
coalesce(pt.modification_date, 0),
rl.bom,
rl.bom_import_done,
rl.sku
FROM pimcore_product_response_line rl
    LEFT JOIN product_template pt on lower(rl.sku) = lower(pt.default_code)
    WHERE rl.state = 'draft';"""
        )
        data = self.env.cr.fetchall()
        skipped = [row[0] for row in data if row[2] <= row[3] and not row[4]]
        updated = [row for row in data if row[2] > row[3]]
        _logger.info("Skipped lines: %d" % len(skipped))
        self.env["pimcore.product.response.line"].browse(skipped).unlink()
        # jobs for import/update products
        for pos in range(0, len(updated), chunk_size):
            self.with_delay().job_import_product_data(updated[pos : pos + chunk_size])
        # job for import bom for lines with bom data not already imported
        bom_lines = [row[0] for row in data if row[4] and not row[5]]
        for pos in range(0, len(bom_lines), chunk_size):
            self.with_delay().job_import_bom(bom_lines[pos : pos + chunk_size])
        # delete older than 14 days data
        self.search(
            [("create_date", "<", datetime.now() - relativedelta(days=14))]
        ).unlink()
        # archive/unarchive products
        do_archive = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("tameson_pimcore.product_archive", "0")
        ) == "1"
        if do_archive:
            self.with_delay().job_archive_unarchive()

    def job_import_product_data(self, lines=()):
        Line = self.env["pimcore.product.response.line"]
        for row in lines:
            line = Line.browse(row[0])
            if not row[1]:
                line.sudo().create_product()
            else:
                line.sudo().update_product(row[1])

    def job_import_bom(self, lines=()):
        lines = self.env["pimcore.product.response.line"].browse(lines)
        for line in lines.exists():
            line.create_bom()

    def job_archive_unarchive(self):
        unpublished = self.env["product.template"].search(
            [("published", "=", False), ("pimcore_id", "!=", False)]
        )
        use_up = self.env["product.template"].search(
            [
                ("t_use_up", "!=", False),
                ("pimcore_id", "!=", False),
                ("minimal_qty_available_stored", "<=", 0),
            ]
        )
        unpublished_products = unpublished + use_up
        unpublished_product_variants = unpublished_products.mapped(
            "product_variant_ids"
        )
        active_products = (
            self.env["stock.move"]
            .search(
                [
                    ("product_id", "in", unpublished_product_variants.ids),
                    ("state", "not in", ("done", "cancel")),
                ]
            )
            .mapped("product_id")
        )
        active_products += (
            self.env["purchase.order.line"]
            .search(
                [
                    ("product_id", "in", unpublished_product_variants.ids),
                    ("state", "=", "draft"),
                ]
            )
            .mapped("product_id")
        )
        active_products += (
            self.env["sale.order.line"]
            .search(
                [
                    ("product_id", "in", unpublished_product_variants.ids),
                    ("state", "=", "draft"),
                ]
            )
            .mapped("product_id")
        )
        active_pts = active_products.mapped("product_tmpl_id")
        _logger.info(
            "%s not archived from pimcore response due to active pos/so/move"
            % active_pts.mapped("default_code")
        )
        unpublished_products = unpublished_products - active_pts
        self.env["stock.warehouse.orderpoint"].search(
            [
                (
                    "product_id",
                    "in",
                    unpublished_products.mapped("product_variant_ids").ids,
                )
            ]
        ).with_delay().action_archive()
        split_size = 100
        for pos in range(0, len(unpublished_products), split_size):
            unpublished_products[pos : pos + split_size].with_delay().action_archive()
        _logger.info(
            "%s archived from pimcore response"
            % unpublished_products.mapped("default_code")
        )
        published_products = self.env["product.template"].search(
            [
                ("published", "=", True),
                ("active", "=", False),
                ("pimcore_id", "!=", False),
            ]
        )
        split_size = 100
        for pos in range(0, len(published_products), split_size):
            published_products[pos : pos + split_size].with_delay().action_unarchive()

        self.env["stock.warehouse.orderpoint"].search(
            [
                ("active", "=", False),
                (
                    "product_id",
                    "in",
                    published_products.mapped("product_variant_ids").ids,
                ),
            ]
        ).with_delay().action_unarchive()
        return "Archived: %s\nUnarchived: %s" % (
            unpublished_products.mapped("default_code"),
            published_products.mapped("default_code"),
        )


class PimcoreProductResponseLine(models.Model):
    _name = "pimcore.product.response.line"
    _description = "PimcoreProductResponseLine"

    state = fields.Selection(
        string="Status",
        default="draft",
        selection=[
            ("draft", "Draft"),
            ("created", "Created"),
            ("updated", "Updated"),
            ("skipped", "Skipped"),
            ("error", "Error"),
        ],
    )
    response_id = fields.Many2one(
        comodel_name="pimcore.product.response",
        ondelete="cascade",
    )
    name = fields.Char()
    name_nl = fields.Char()
    name_de = fields.Char()
    name_es = fields.Char()
    name_fr = fields.Char()
    pimcore_id = fields.Char()
    full_path = fields.Char()
    categories = fields.Char()
    supplier_email = fields.Char()
    supplier_part_number = fields.Char()
    supplier_price_currency = fields.Char()
    supplier_lead_time = fields.Integer()
    customer_lead_time = fields.Integer()
    sku = fields.Char()
    ean = fields.Char()
    intrastat = fields.Char()
    image = fields.Char()
    bom = fields.Char()
    width = fields.Float()
    height = fields.Float()
    depth = fields.Float()
    weight = fields.Float()
    volume = fields.Float()
    modification_date = fields.Float()
    eur = fields.Float()
    supplier_price = fields.Float()
    bom_import_done = fields.Boolean(default=False)
    use_up = fields.Boolean()
    backorder = fields.Boolean()
    oversized = fields.Boolean()
    non_returnable = fields.Boolean()
    imperial = fields.Boolean()
    web_sales = fields.Boolean()
    published = fields.Boolean()
    error = fields.Text()
    short_description = fields.Text()
    replacement_sku = fields.Char()
    origin_country = fields.Char()
    brand_name = fields.Char()
    manufacturer_name = fields.Char()
    mpn = fields.Char()
    pack_model = fields.Char()
    pack_factor = fields.Float()
    sticker_barcode = fields.Char()
    max_qty_order = fields.Integer()
    min_qty_order = fields.Integer()
    supplier_series = fields.Char()
    supplier_shipping_type = fields.Char()
    supplier_package_qty = fields.Integer()
    additional_cost = fields.Char()
    fragile = fields.Boolean()
    supplier_list_price = fields.Float()
    draft = fields.Boolean()

    @api.model_create_multi
    def create(self, vals):
        return super(PimcoreProductResponseLine, self).create(vals)

    def create_product(self):
        self.env["product.category"]
        image_data = False
        if self.image:
            image_response = requests.get(self.image, timeout=60)
            if image_response.status_code == 200:
                image_data = codecs.encode(image_response.content, "base64")
        vals = self.get_product_vals()
        final_categ = create_or_find_categ(self.env, self.full_path)
        ecom_categ = create_or_find_categ(
            self.env,
            self.categories,
            model="product.public.category",
            start=2,
            end=0,
        )
        price = (
            self.env["res.currency"]
            .browse(CURRENCY_DICT[self.supplier_price_currency])
            ._convert(
                self.supplier_price,
                self.env.user.company_id.currency_id,
                self.env.user.company_id,
                self.create_date,
            )
        )
        vals.update(
            {
                "image_1920": image_data,
                "categ_id": final_categ.id,
                "public_categ_ids": [(6, 0, ecom_categ.ids)],
                "list_price": self.eur,
                "standard_price": price,
                "supplier_series": self.supplier_series,
            }
        )
        if self.supplier_email:
            vals.update(
                {
                    "seller_ids": [(0, 0, self.get_supplier_info())],
                }
            )
        try:
            product = self.env["product.template"].create(vals)
        except UniqueViolation as e:
            _logger.info(e)
            barcode = self.ean
            bproduct = self.env["product.product"].search([("barcode", "=", barcode)])
            bproduct.write(
                {
                    "barcode": False,
                    "modification_date": 0,
                }
            )
            product = self.env["product.template"].create(vals)
        product.update_field_translations(
            "name",
            {
                "nl_NL": self.name_nl,
                "fr_FR": self.name_fr,
                "de_DE": self.name_de,
                "es_ES": self.name_es,
            },
        )
        self.write(
            {
                "state": "created",
            }
        )

    def update_product(self, product_id):
        product = self.env["product.template"].browse(product_id)
        vals = self.get_product_vals()
        product.update_field_translations(
            "name",
            {
                "nl_NL": self.name_nl,
                "fr_FR": self.name_fr,
                "de_DE": self.name_de,
                "es_ES": self.name_es,
            },
        )
        if product.categ_id.name != self.full_path.split("/")[-2]:
            final_categ = create_or_find_categ(self.env, self.full_path)
            vals.update(categ_id=final_categ.id)

        if self.supplier_email:
            seller_vals = self.get_supplier_info()
            seller = product.seller_ids.filtered(
                lambda s: s.partner_id.id == seller_vals["partner_id"]
            )
            if not seller:
                product.seller_ids.unlink()
                vals.update(seller_ids=[(0, 0, seller_vals)])
        if (
            self.categories
            and product.public_categ_ids[:1].name != self.categories.split("/")[-1]
        ):
            ecom_categ = create_or_find_categ(
                self.env,
                self.categories,
                model="product.public.category",
                start=2,
                end=0,
            )
            vals.update(public_categ_ids=[(6, 0, ecom_categ.ids)])
        write_vals = {"state": "updated"}
        try:
            product.write(vals)
        except UniqueViolation as e:
            _logger.info(e)
            barcode = self.ean
            bproduct = self.env["product.product"].search([("barcode", "=", barcode)])
            bproduct.write(
                {
                    "barcode": False,
                    "modification_date": 0,
                }
            )
            product.write(vals)
        self.write(write_vals)

    def get_product_vals(self):
        commodity_code = self.env["account.intrastat.code"].search(
            [("code", "=", self.intrastat[:8]), ("type", "=", "commodity")], limit=1
        )
        if not commodity_code:
            commodity_code = self.env["account.intrastat.code"].create(
                {
                    "type": "commodity",
                    "code": (self.intrastat or "")[:8],
                    "description": "new from pimcore",
                }
            )
        origin = self.env["res.country"].search(
            [("code", "=", self.origin_country)], limit=1
        )
        data = {
            "name": self.name,
            "pimcore_id": self.pimcore_id,
            "default_code": self.sku,
            "barcode": self.ean,
            "weight": self.weight / 1000,
            "t_height": self.height,
            "t_length": self.depth,
            "t_width": self.width,
            "type": "product",
            "modification_date": self.modification_date,
            "hs_code": self.intrastat,
            "intrastat_code_id": commodity_code.id,
            "t_product_description_short": self.short_description,
            "t_use_up": self.use_up,
            "purchase_ok": not self.use_up,
            "t_use_up_replacement_sku": self.replacement_sku,
            "intrastat_origin_country_id": origin.id,
            "t_customer_backorder_allowed": self.backorder,
            "brand_name": self.brand_name,
            "manufacturer_name": self.manufacturer_name,
            "manufacturer_pn": self.mpn,
            "oversized": self.oversized,
            "imperial": self.imperial,
            "non_returnable": self.non_returnable,
            "t_web_sales": self.web_sales,
            "published": self.published,
            "full_path": self.full_path,
            "category_path": self.categories,
            "pack_model": self.pack_model,
            "pack_factor": self.pack_factor,
            "sticker_barcode": self.sticker_barcode,
            "supplier_shipping_type": self.supplier_shipping_type,
            "additional_cost": self.additional_cost,
            "fragile": self.fragile,
        }
        if not self.bom:
            data.update(
                {
                    "max_qty_order": self.max_qty_order,
                    "min_qty_order": self.min_qty_order,
                    "supplier_shipping_type": self.supplier_shipping_type,
                }
            )
        return data

    def create_bom(self, bom_type="phantom"):
        PT = self.env["product.template"]
        main_product = PT.with_context(active_test=False).search(
            [("default_code", "=", self.sku)], limit=1
        )
        matched_bom = main_product.bom_ids.filtered(
            lambda b: b.bom_signature == self.bom
        )[:1]
        if matched_bom:
            try:
                (main_product.bom_ids - matched_bom).action_archive()
            except Exception as e:
                _logger.warn(e)
            matched_bom.action_unarchive()
            return
        if main_product.bom_ids:
            main_product.bom_ids.write({"sequence": 1000})
            try:
                main_product.bom_ids.action_archive()
            except Exception as e:
                _logger.warn(e)
        bom_elements = self.bom.split(",")
        bom_lines = []
        for i in range(0, len(bom_elements), 2):
            bom_item = PT.with_context(active_test=False).search(
                [("default_code", "=", bom_elements[i])], limit=1
            )
            bom_qty = bom_elements[i + 1]
            bom_lines.append(
                (
                    0,
                    0,
                    {
                        "product_id": bom_item.product_variant_id.id,
                        "product_qty": float(bom_qty),
                    },
                )
            )
        self.env["mrp.bom"].create(
            {
                "product_tmpl_id": main_product.id,
                "bom_line_ids": bom_lines,
                "type": bom_type,
                "bom_signature": self.bom,
                "sequence": 10,
            }
        )
        self.write({"bom_import_done": True})

    def get_supplier_info(self):
        vendor = self.env["res.partner"]
        if self.supplier_email:
            vendor = vendor.search([("email", "=", self.supplier_email)], limit=1)
        if not vendor:
            raise UserError(
                "No vendor partner found for email: %s" % self.supplier_email
            )
        return {
            "partner_id": vendor.id,
            "product_code": self.supplier_part_number,
            "delay": self.supplier_lead_time,
            "min_qty": self.supplier_package_qty,
            "price": self.supplier_price,
            "currency_id": CURRENCY_DICT[self.supplier_price_currency],
            "list_price_eur": self.supplier_list_price,
        }
