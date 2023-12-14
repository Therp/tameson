from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    supplierinfo_name = fields.Char(
        related="product_id.supplierinfo_name", string="Supplier"
    )
