# Copyright 2020 Therp BV <https://therp.nl>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models, fields


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    ungrouped_origin = fields.Many2one(
        'sale.order',
        help="""the origin of this purchase order line,
                is set only for ungrouped lines deriving from sales orders
                a sales order"""
    )

    def _find_candidate(
           self, product_id, product_qty, product_uom, location_id, name,
           origin, company_id, values):
        if (values.get("grouping") == "line_specific" and
                self.order_id.partner_id.no_grouping_po_lines):
            origin = self.env['sale.order'].search([
                ('name', '=', origin)], limit=1)
            if origin:
                self.write({'ungrouped_origin': origin.id})
            return False
        return super()._find_candidate(
                product_id,
                product_qty,
                product_uom,
                location_id,
                name,
                origin,
                company_id,
                values,
            )
