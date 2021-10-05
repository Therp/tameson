# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import requests, codecs
from datetime import datetime
from odoo.tools.float_utils import float_is_zero, float_compare
from dateutil.relativedelta import relativedelta

import logging
_logger = logging.getLogger(__name__)

CURRENCY_DICT = {"USD": 3, "EUR": 1, "GBP": 150}


def create_or_find_categ(env, path, model="product.category", start=3, end=-1):
    if end == 0:
        end = len(path.split("/"))
    categ_path = path.split("/")[start:end]
    child_categ = env[model]
    final_categ = env[model]
    for categ in categ_path[::-1]:
        break_loop = False
        this_categ = child_categ.search([("name", "=", categ)], limit=1)
        if not this_categ:
            this_categ = child_categ.create({"name": categ})
        else:
            break_loop = True
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


def add_pricelist_item(pricelist, product, price):
    pricelist.write(
        {
            "item_ids": [
                (
                    0,
                    0,
                    {
                        "applied_on": "1_product",
                        "product_tmpl_id": product.id,
                        "compute_price": "fixed",
                        "fixed_price": price,
                    },
                )
            ]
        }
    )


def search_or_add_pricelist_item(pricelist, product, price):
    item = pricelist.env["product.pricelist.item"].search(
        [
            ("applied_on", "=", "1_product"),
            ("product_tmpl_id", "=", product.id),
            ("pricelist_id", "=", pricelist.id),
        ],
        limit=1,
    )
    if item:
        if not float_compare(item.fixed_price, price, precision_digits=2) == 0:
            item.write({"fixed_price": price})
    else:
        add_pricelist_item(pricelist, product, price)


class PimcoreProductResponse(models.Model):
    _name = "pimcore.product.response"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "PimcoreProductResponse"

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

    def import_product_data(self):
        self.env.cr.execute(
            """
        select rl.id, pt.id, rl.modification_date, coalesce(pt.modification_date, 0) from pimcore_product_response_line rl
        left join product_template pt on lower(rl.sku) = lower(pt.default_code)
        where rl.state = 'draft'
        """
        )
        data = self.env.cr.fetchall()
        skipped = [row[0] for row in data if row[2] <= row[3]]
        updated = [row for row in data if row[2] > row[3]]
        _logger.warn("Skipped lines: %d" % len(skipped))
        Line = self.env["pimcore.product.response.line"]
        self.env["pimcore.product.response.line"].browse(skipped).unlink()
        Eur = self.env["product.pricelist"].search(
            [("currency_id", "=", "EUR")], limit=1
        )
        Gbp = self.env["product.pricelist"].search(
            [("currency_id", "=", "GBP")], limit=1
        )
        Usd = self.env["product.pricelist"].search(
            [("currency_id", "=", "USD")], limit=1
        )
        _logger.warn("Start importing data from %d lines" % len(updated))
        for count, row in enumerate(updated):
            try:
                if not row[1]:
                    Line.browse(row[0]).create_product(Eur, Gbp, Usd)
                    _logger.warn("Created from %d / %d " % (count, len(updated)))
                elif row[2] > row[3]:
                    Line.browse(row[0]).update_product(row[1], Eur, Gbp, Usd)
                    _logger.warn("Updated from %d / %d " % (count, len(updated)))
            except Exception as e:
                _logger.warn(str(e))
                Line.browse(row[0]).write({"state": "error", "error": str(e)})
        bomlines = Line.search(
            [
                ("bom_import_done", "=", False),
                ("bom", "!=", False),
                ("state", "=", "created"),
            ]
        )
        for line in bomlines:
            try:
                line.create_bom()
            except Exception as e:
                line.write({"state": "error", "error": str(e)})
                _logger.warn(str(e))
                continue
        self.search(
            [("create_date", "<", datetime.now() - relativedelta(days=14))]
        ).unlink()


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
    wholesaleprice = fields.Float()
    gbp = fields.Float()
    usd = fields.Float()
    supplier_price = fields.Float()
    bom_import_done = fields.Boolean()
    use_up = fields.Boolean()
    backorder = fields.Boolean()
    oversized = fields.Boolean()
    non_returnable = fields.Boolean()
    imperial = fields.Boolean()
    web_sales = fields.Boolean()
    error = fields.Text()
    short_description = fields.Text()
    replacement_sku = fields.Char()
    origin_country = fields.Char()
    brand_name = fields.Char()
    manufacturer_name = fields.Char()
    mpn = fields.Char()

    def create_product(self, Eur, Gbp, Usd):
        Category = self.env["product.category"]
        image_response = requests.get(
            "%s/%s" % (self.response_id.config_id.api_host, self.image)
        )
        if image_response.status_code == 200:
            image_data = codecs.encode(image_response.content, "base64")
        else:
            image_data = False

        vals = self.get_product_vals()
        final_categ = create_or_find_categ(self.env, self.full_path)
        ecom_categ = create_or_find_categ(
            self.env, self.categories, model="product.public.category", start=2, end=0
        )
        vals.update(
            {
                "image_1920": image_data,
                "categ_id": final_categ.id,
                "public_categ_ids": [(6, 0, ecom_categ.ids)],
            }
        )
        if self.supplier_email:
            vals.update(
                {
                    "seller_ids": [(0, 0, self.get_supplier_info())],
                }
            )
        product = self.env["product.template"].create(vals)
        add_translation(self.env, product, "nl_NL", self.name, self.name_nl)
        add_translation(self.env, product, "fr_FR", self.name, self.name_fr)
        add_translation(self.env, product, "de_DE", self.name, self.name_de)
        add_translation(self.env, product, "es_ES", self.name, self.name_es)
        add_pricelist_item(Eur, product, self.wholesaleprice / 100)
        add_pricelist_item(Gbp, product, self.gbp)
        add_pricelist_item(Usd, product, self.usd)
        self.write({"state": "created"})
        self.env.cr.commit()

    def update_product(self, product_id, Eur, Gbp, Usd):
        product = self.env["product.template"].browse(product_id)
        vals = self.get_product_vals()
        if not float_is_zero(product.standard_price, precision_digits=2):
            vals.pop("standard_price")
        add_translation(self.env, product, "nl_NL", self.name, self.name_nl)
        add_translation(self.env, product, "fr_FR", self.name, self.name_fr)
        add_translation(self.env, product, "de_DE", self.name, self.name_de)
        add_translation(self.env, product, "es_ES", self.name, self.name_es)

        if product.categ_id.name != self.full_path.split("/")[-2]:
            final_categ = create_or_find_categ(self.env, self.full_path)
            vals.update(categ_id=final_categ.id)

        if self.supplier_email:
            seller_vals = self.get_supplier_info()
            seller_vals.pop("price")
            seller = product.seller_ids.filtered(
                lambda s: s.name.id == seller_vals["name"]
            )[:1]
            if seller:
                seller.write(seller_vals)
            else:
                vals.update(seller_ids=[(0, 0, seller_vals)])
        if product.public_categ_ids[:1].name != self.categories.split("/")[-1]:
            ecom_categ = create_or_find_categ(
                self.env,
                self.categories,
                model="product.public.category",
                start=2,
                end=0,
            )
            vals.update(public_categ_ids=[(6, 0, ecom_categ.ids)])
        search_or_add_pricelist_item(Gbp, product, self.gbp)
        search_or_add_pricelist_item(Usd, product, self.usd)
        product.write(vals)
        self.write({"state": "updated"})
        self.env.cr.commit()

    def get_product_vals(self):
        commodity_code = self.env["account.intrastat.code"].search(
            [("code", "=", self.intrastat[:8]), ("type", "=", "commodity")], limit=1
        )
        if not commodity_code:
            commodity_code = self.env["account.intrastat.code"].create(
                {
                    "type": "commodity",
                    "code": self.intrastat[:8],
                    "description": "new from pimcore",
                }
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
        origin = self.env["res.country"].search(
            [("code", "=", self.origin_country)], limit=1
        )
        return {
            "name": self.name,
            "pimcore_id": self.pimcore_id,
            "default_code": self.sku,
            "barcode": self.ean,
            "weight": self.weight / 1000,
            "t_height": self.height,
            "t_length": self.depth,
            "t_width": self.width,
            "type": "product",
            "list_price": self.wholesaleprice / 100,
            "modification_date": self.modification_date,
            "hs_code": self.intrastat,
            "intrastat_id": commodity_code.id,
            "t_product_description_short": self.short_description,
            "t_use_up": self.use_up,
            "standard_price": price,
            "t_use_up_replacement_sku": self.replacement_sku,
            "intrastat_origin_country_id": origin.id,
            "t_customer_backorder_allowed": self.backorder,
            "t_customer_lead_time": self.customer_lead_time,
            "brand_name": self.brand_name,
            "manufacturer_name": self.manufacturer_name,
            "manufacturer_pn": self.mpn,
            "oversized": self.oversized,
            "imperial": self.imperial,
            "non_returnable": self.non_returnable,
            "t_web_sales": self.web_sales,
        }

    def create_bom(self, bom_type="phantom"):
        PT = self.env["product.template"]
        main_product = PT.search([("default_code", "=", self.sku)], limit=1)
        bom_elements = self.bom.split(",")
        bom_lines = []
        for i in range(0, len(bom_elements), 2):
            bom_item = PT.search([("default_code", "=", bom_elements[i])], limit=1)
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
            }
        )
        main_product.standard_price = (
            main_product.product_variant_id._get_price_from_bom()
        )
        self.bom_import_done = True
        self.env.cr.commit()

    def get_supplier_info(self):
        vendor = self.env["res.partner"]
        if self.supplier_email:
            vendor = vendor.search([("email", "=", self.supplier_email)], limit=1)
        if not vendor:
            raise UserError(
                "No vendor partner found for email: %s" % self.supplier_email
            )
        return {
            "name": vendor.id,
            "product_code": self.supplier_part_number,
            "delay": self.supplier_lead_time,
            "min_qty": 1,
            "price": self.supplier_price,
            "currency_id": CURRENCY_DICT[self.supplier_price_currency],
        }
