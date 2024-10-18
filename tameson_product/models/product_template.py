import json

from odoo import api, fields, models, tools
from odoo.tools.float_utils import float_compare


class ProductTemplateInherit(models.Model):
    _name = "product.template"
    _inherit = ["product.template", "set.help.mixin"]

    def init(self):
        res = super(ProductTemplateInherit, self).init()

        default_code_index = "product_template_default_code_unique_idx"
        if not tools.index_exists(self._cr, default_code_index):
            self._cr.execute(
                """
CREATE UNIQUE INDEX IF NOT EXISTS {} ON {} ((lower(default_code)))
WHERE active = true
AND default_code != ''
AND default_code IS NOT NULL""".format(
                    default_code_index, self._table
                )
            )

        return res

    supplierinfo_name = fields.Char(
        string="Vendor Name",
        compute="_compute_supplierinfo_fields",
        store=True,
    )
    supplierinfo_code = fields.Char(
        string="Vendor SKU",
        compute="_compute_supplierinfo_fields",
        store=True,
    )
    supplierinfo_delay = fields.Integer(
        string="Vendor Delivery Lead Time",
        compute="_compute_supplierinfo_fields",
        store=True,
    )
    t_aa_pack_size = fields.Float(string="Pack size", compute="_get_aa_packing_size")

    t_location = fields.Char(string="Location Tameson", required=False)

    t_product_description_short = fields.Text(
        string="Product Description Short", required=False, translate=True
    )
    t_customer_backorder_allowed = fields.Boolean(
        string="Customer backorder allowed", required=False
    )
    t_customer_lead_time = fields.Integer(string="Customer lead time", required=False)
    t_web_sales = fields.Boolean(string="WebSales", required=False)
    t_use_up = fields.Boolean(string="useUp", required=False)
    t_use_up_replacement_sku = fields.Char(
        string="Use up replacement SKU", required=False
    )
    t_height = fields.Float(string="Height (in mm)", required=False)
    t_length = fields.Float(string="Length (in mm)", required=False)
    t_width = fields.Float(string="Width (in mm)", required=False)

    # Pimcore fields
    modification_date = fields.Float()
    pimcore_id = fields.Char("Pimcore ID")
    brand_name = fields.Char("Brand name")
    full_path = fields.Char("Full Path")
    category_path = fields.Char("Category Path")
    manufacturer_name = fields.Char("Manufacturer")
    manufacturer_pn = fields.Char("Manufacturer Part Number ")
    oversized = fields.Boolean(string="Oversized")
    imperial = fields.Boolean(string="Imperial")
    published = fields.Boolean(string="Pimcore Published", default=True)
    non_returnable = fields.Boolean(string="Non Returnable")
    pack_model = fields.Char()
    pack_factor = fields.Float()
    usd_extra_price_factor = fields.Float(default=1.0)
    sticker_barcode = fields.Char()
    max_qty_order = fields.Integer(help='Max quantity for "Customer lead time"')
    max_qty_order_array = fields.Char()
    min_qty_order = fields.Integer()
    supplier_series = fields.Char()
    supplier_shipping_type = fields.Char()
    additional_cost = fields.Char()
    fragile = fields.Boolean()
    # End
    extra_shipping_fee_usd = fields.Float(string="Extra shipping fee USD", default=0.0)
    extra_shipping_fee_gbp = fields.Float(string="Extra shipping fee GBP", default=0.0)
    margin_eur_group = fields.Float()
    sale_price_usd = fields.Float(string="Sale Price USD")
    sale_price_gbp = fields.Float(string="Sale Price GBP")

    def cron_compute_all_bom_price(self):
        boms = (
            self.env["mrp.bom"].search([]).filtered(lambda b: b.product_tmpl_id.active)
        )
        for bom in boms:
            product_tmpl_id = bom.product_tmpl_id
            product = product_tmpl_id.product_variant_id
            product_tmpl_id.standard_price = product._compute_bom_price(bom)

    @api.depends("bom_ids.bom_line_ids")
    def _get_aa_packing_size(self):
        for pt in self:
            if pt.bom_ids and len(pt.bom_ids[:1].bom_line_ids) == 1:
                pt.t_aa_pack_size = pt.bom_ids[:1].bom_line_ids.product_qty
            else:
                pt.t_aa_pack_size = 1

    @api.depends("seller_ids.partner_id", "seller_ids.product_code", "seller_ids.delay", "bom_ids.bom_line_ids.product_id")
    def _compute_supplierinfo_fields(self):
        for product in self:
            first_supplier = product.seller_ids.sorted()[:1]
            if first_supplier:
                product.supplierinfo_name = first_supplier.partner_id.name
                product.supplierinfo_code = first_supplier.product_code
                product.supplierinfo_delay = first_supplier.delay
            elif product.bom_ids:
                components_sellers = set(
                    product.bom_ids[:1].bom_line_ids.mapped(
                        "product_id.supplierinfo_name"
                    )
                )
                product.supplierinfo_name = ','.join(list(components_sellers))
                product.supplierinfo_code = ''
                product.supplierinfo_delay = 0
            else:
                product.supplierinfo_name = ''
                product.supplierinfo_code = ''
                product.supplierinfo_delay = 0


    def set_updated_product_bom_price(self, split=2000):
        n_days = 2
        BOM = self.env["mrp.bom"]
        updated_bom_query = """
select distinct boms.id from (
SELECT mb.id FROM product_product pp
    LEFT JOIN product_template pt on pp.product_tmpl_id = pt.id
    LEFT JOIN mrp_bom_line bl ON bl.product_id = pp.id
    LEFT JOIN mrp_bom mb ON mb.id = bl.bom_id
    WHERE pt.write_date >= current_date - interval '%(n_days)d' day
    OR pp.write_date >= current_date - interval '%(n_days)d' day
union
SELECT id from mrp_bom
    Where write_date >= current_date - interval '%(n_days)d' day) as boms
""" % {
            "n_days": n_days
        }
        self.env.cr.execute(updated_bom_query)
        boms = BOM.browse([item[0] for item in self.env.cr.fetchall()])
        boms.set_bom_price(split)

    def set_all_product_bom_price(self, split=2000):
        boms = self.env["mrp.bom"].search([])
        boms.set_bom_price(split)
        self.set_all_margin_eur_group()

    def set_non_bom_lead(self):
        for pt in self:
            delay = pt.seller_ids[:1].delay + 1
            if pt.minimal_qty_available_stored > 0:
                delay_array = [
                    {"lead_time": 0, "max_qty": pt.minimal_qty_available_stored},
                    {
                        "lead_time": delay,
                        "max_qty": (pt.minimal_qty_available_stored + pt.max_qty_order),
                    },
                ]
                delay = 0
            else:
                delay_array = [{"lead_time": delay, "max_qty": pt.max_qty_order}]
            pt.write(
                {
                    "t_customer_lead_time": delay,
                    "max_qty_order_array": json.dumps(delay_array),
                }
            )

    def set_all_margin_eur_group(self, n=25000):
        products = self.search([])
        for pos in range(0, len(products), n):
            products[pos : pos + n].with_delay().set_margin_eur_group()

    def set_margin_eur_group(self):
        for product in self:
            margin = (product.list_price - product.standard_price) / 10
            if float_compare(product.margin_eur_group, margin, precision_digits=2) != 0:
                product.write({"margin_eur_group": margin})


class Product(models.Model):
    _name = "product.product"
    _inherit = ["product.product", "set.help.mixin"]
