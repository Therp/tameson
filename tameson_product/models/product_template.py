from odoo import api, fields, models, tools, _
from odoo.tools.float_utils import float_is_zero


class ProductTemplateInherit(models.Model):
    _name = "product.template"
    _inherit = ["product.template", "set.help.mixin"]

    def init(self):
        res = super(ProductTemplateInherit, self).init()

        default_code_index = "product_template_default_code_unique_idx"
        if not tools.index_exists(self._cr, default_code_index):
            self._cr.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS {} ON {} ((lower(default_code))) WHERE active = true AND default_code != '' AND default_code IS NOT NULL".format(
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

    t_location = fields.Char(string=_("Location Tameson"), required=False)

    t_product_description_short = fields.Text(
        string=_("Product Description Short"), required=False, translate=True
    )
    t_customer_backorder_allowed = fields.Boolean(
        string=_("Customer backorder allowed"), required=False
    )
    t_customer_lead_time = fields.Integer(
        string=_("Customer lead time"), required=False
    )
    t_web_sales = fields.Boolean(string=_("WebSales"), required=False)
    t_use_up = fields.Boolean(string=_("useUp"), required=False)
    t_use_up_replacement_sku = fields.Char(
        string=_("Use up replacement SKU"), required=False
    )
    t_height = fields.Float(string=_("Height (in mm)"), required=False)
    t_length = fields.Float(string=_("Length (in mm)"), required=False)
    t_width = fields.Float(string=_("Width (in mm)"), required=False)

    ## Pimcore fields
    modification_date = fields.Float()
    pimcore_id = fields.Char("Pimcore ID")
    brand_name = fields.Char("Brand name")
    full_path = fields.Char("Full Path")
    category_path = fields.Char("Category Path")
    manufacturer_name = fields.Char("Manufacturer")
    manufacturer_pn = fields.Char("Manufacturer Part Number ")
    oversized = fields.Boolean(string=_("Oversized"))
    imperial = fields.Boolean(string=_("Imperial"))
    published = fields.Boolean(string=_("Published"), default=True)
    non_returnable = fields.Boolean(string=_("Non Returnable"))
    pack_model = fields.Char()
    pack_factor = fields.Float()
    usd_extra_price_factor = fields.Float(default=1.0)
    sticker_barcode = fields.Char()
    max_qty_order = fields.Integer(help="Max quantity for \"Customer lead time\"")
    max_qty_order_array = fields.Char()
    min_qty_order = fields.Integer()
    supplier_series = fields.Char()
    supplier_shipping_type = fields.Char()
    additional_cost = fields.Char()
    ## End

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

    @api.depends("seller_ids.name", "seller_ids.product_code", "seller_ids.delay")
    def _compute_supplierinfo_fields(self):
        for product in self:
            first_supplier = product.seller_ids.sorted()[:1]
            if first_supplier:
                product.supplierinfo_name = first_supplier.name.name
                product.supplierinfo_code = first_supplier.product_code
                product.supplierinfo_delay = first_supplier.delay

    def set_updated_product_bom_price(self):
        n_days = 2
        BOM = self.env['mrp.bom']
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
""" % {'n_days': n_days}
        self.env.cr.execute(updated_bom_query)
        boms = BOM.browse([item[0] for item in self.env.cr.fetchall()])
        boms.set_bom_sale_price()

    def set_all_product_bom_price(self):
        boms = self.env["mrp.bom"].search([])
        boms.set_bom_sale_price()
        for pos in range(0, len(boms), 5000):
            boms[pos:pos+5000].with_delay().set_bom_cost_price_job()

    def set_non_bom_lead(self):
        for pt in self:
            if not self.bom_ids:
                if not float_is_zero(pt.minimal_qty_available_stored, precision_digits=2):
                    delay = 0
                else:
                    delay = pt.seller_ids[:1].delay
                pt.write({'t_customer_lead_time': delay + 1})
