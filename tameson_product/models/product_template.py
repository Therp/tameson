from odoo import api, fields, models, _


class ProductTemplateInherit(models.Model):
    _inherit = "product.template"

    supplierinfo_name = fields.Char(
        string="Vendor Name",
        compute='_compute_supplierinfo_fields',
        store=True,
    )
    supplierinfo_code = fields.Char(
        string="Vendor SKU",
        compute='_compute_supplierinfo_fields',
        store=True,
    )
    supplierinfo_delay = fields.Integer(
        string="Vendor Delivery Lead Time",
        compute='_compute_supplierinfo_fields',
        store=True,
    )

    @api.depends('seller_ids.name', 'seller_ids.product_code', 'seller_ids.delay')
    def _compute_supplierinfo_fields(self):
        for product in self:
            first_supplier = product.seller_ids.sorted()[:1]
            if first_supplier:
                product.supplierinfo_name = first_supplier.name.name
                product.supplierinfo_code = first_supplier.product_code
                product.supplierinfo_delay = first_supplier.delay
