from odoo import api, fields, models, _


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    t_location = fields.Char(
        string=_('Location Tameson'),
        required=False)

    t_product_description_short = fields.Text(
        string=_('Product Description Short'),
        required=False,
        translate=True
    )
    t_customer_backorder_allowed = fields.Boolean(
        string=_('Customer backorder allowed'),
        required=False
    )
    t_customer_lead_time = fields.Integer(
        string=_('Customer lead time'),
        required=False
    )
    t_web_sales = fields.Boolean(
        string=_('WebSales'),
        required=False
    )
    t_use_up = fields.Boolean(
        string=_('useUp'),
        required=False
    )
    t_use_up_replacement_sku = fields.Char(
        string=_('Use up replacement SKU'),
        required=False
    )
    t_height = fields.Float(
        string=_('Height (in mm)'),
        required=False
    )
    t_length = fields.Float(
        string=_('Length (in mm)'),
        required=False
    )
    t_width = fields.Float(
        string=_('Width (in mm)'),
        required=False
    )

## Pimcore fields
    modification_date = fields.Float()
    pimcore_id = fields.Char("Pimcore ID")
    brand_name = fields.Char("Brand name")
    full_path = fields.Char("Full Path")
    category_path = fields.Char("Category Path")
    manufacturer_name = fields.Char("Manufacturer")
    manufacturer_pn = fields.Char("Manufacturer Part Number ")
    oversized = fields.Boolean(string=_('Oversized'))
    imperial = fields.Boolean(string=_('Imperial'))
    published = fields.Boolean(string=_('Published'), default=True)
    non_returnable = fields.Boolean(string=_('Non Returnable'))
    pack_model = fields.Char()
    pack_factor = fields.Float()
    sticker_barcode = fields.Char()
## End

    def cron_compute_all_bom_price(self):
        boms = self.env['mrp.bom'].search([]).filtered(lambda b: b.product_tmpl_id.active)
        for bom in boms:
            product_tmpl_id = bom.product_tmpl_id
            product = product_tmpl_id.product_variant_id
            product_tmpl_id.standard_price = product._compute_bom_price(bom)
