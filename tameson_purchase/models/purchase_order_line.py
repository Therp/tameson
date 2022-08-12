# Copyright 2020 Therp BV <https://therp.nl>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models, fields, _


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    ungrouped_origin = fields.Many2one(
        "sale.order",
        help="The origin of this purchase order line,"
        "is set only for ungrouped lines deriving from sales orders",
    )

    def _find_candidate(
        self,
        product_id,
        product_qty,
        product_uom,
        location_id,
        name,
        origin,
        company_id,
        values,
    ):
        if (
            values.get("grouping") == "line_specific"
            and self.order_id.partner_id.no_grouping_po_lines
        ):
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

    minimal_qty_available = fields.Float(
        related="product_id.minimal_qty_available",
        string=_("Product min qty available"),
        readonly=True,
    )
    
    max_reorder = fields.Float(compute='_get_max_reorder', digits=(4,2))
    max_reorder_percentage = fields.Float(compute='_get_max_reorder', digits=(4,2))
    
    def _get_max_reorder(self):
        for line in self:
            reorder = line.product_id.orderpoint_ids[:1]
            if not reorder:
                line.max_reorder = 0
                line.max_reorder_percentage = 0
            else:
                line.max_reorder = reorder.product_max_qty
                line.max_reorder_percentage = reorder.product_max_qty / reorder.product_min_qty * 100
    
    incoming_qty = fields.Float(related='product_id.incoming_qty')
    outgoing_qty = fields.Float(related='product_id.outgoing_qty')
