# Copyright 2020 Therp BV <https://therp.nl>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def find_and_refresh_picking_in_out_associations(self):
        for this in self:
            for line in this.order_line:
                # PO of POL
                # connected Sale for POL (only ongrouped origin)
                sale = line.ungrouped_origin
                if sale:
                    # picking type code = incoming
                    # we use the features from purchase_stock and sale_stock
                    # get the move of the picking associated with current POL
                    all_in_moves = this.picking_ids.move_lines
                    in_moves = self.env["stock.move"].search(
                        [
                            ("id", "in", all_in_moves.ids),
                            ("picking_code", "=", "incoming"),
                            ("purchase_line_id", "=", line.id),
                        ]
                    )
                    out_pickings = sale.picking_ids.filtered(
                        lambda l: l.move_lines.sale_line_id.order_id == sale
                    )
                    in_moves.write(
                        {"origin_so_picking_ids": [(6, 0, out_pickings.ids)]}
                    )
