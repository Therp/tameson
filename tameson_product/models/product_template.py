from odoo import api, fields, models, tools, _


class ProductTemplateInherit(models.Model):
    _inherit = "product.template"

    def _auto_init(self):
        res = super(ProductTemplateInherit, self)._auto_init()

        default_code_index = 'default_code_unique_idx'
        if not tools.index_exists(self._cr, default_code_index, self._table):
            self._cr.execute('CREATE UNIQUE INDEX {} ON {} (default_code) WHERE active = true'.format(default_code_index, self._table))

        return res

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
