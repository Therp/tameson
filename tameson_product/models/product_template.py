from odoo import api, fields, models, tools, _


class ProductTemplateInherit(models.Model):
    _name = "product.template"
    _inherit = ["product.template", "set.help.mixin"]

    def init(self):
        res = super(ProductTemplateInherit, self).init()

        default_code_index = 'product_template_default_code_unique_idx'
        if not tools.index_exists(self._cr, default_code_index):
            self._cr.execute(
                'CREATE UNIQUE INDEX IF NOT EXISTS {} ON {} ((lower(default_code))) WHERE active = true AND default_code != \'\' AND default_code IS NOT NULL'.format(default_code_index, self._table)
            )

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
    t_aa_pack_size = fields.Float(string='Pack size', compute='_get_aa_packing_size')

    @api.depends('bom_ids.bom_line_ids')
    def _get_aa_packing_size(self):
        for pt in self:
            if pt.bom_ids and len(pt.bom_ids[:1].bom_line_ids) == 1:
                pt.t_aa_pack_size = pt.bom_ids[:1].bom_line_ids.product_qty
            else:
                pt.t_aa_pack_size = 1

    @api.depends('seller_ids.name', 'seller_ids.product_code', 'seller_ids.delay')
    def _compute_supplierinfo_fields(self):
        for product in self:
            first_supplier = product.seller_ids.sorted()[:1]
            if first_supplier:
                product.supplierinfo_name = first_supplier.name.name
                product.supplierinfo_code = first_supplier.product_code
                product.supplierinfo_delay = first_supplier.delay
