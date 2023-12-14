###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    picking_move_type = fields.Selection(
        related="picking_id.move_type", stored=True, index=True
    )
    unknown_date_incoming = fields.Boolean()

    def write(self, vals):
        res = super(StockMove, self).write(vals)
        if "unknown_date_incoming" in vals:
            unknown_date_incoming = vals.get("unknown_date_incoming")
            pickings = self.mapped("move_dest_ids.picking_id").filtered(
                lambda p: p.state not in ("done", "cancel")
            )
            if pickings:
                pickings.write({"unknown_date": unknown_date_incoming})
            else:
                product_moves = self.env["stock.move"].search(
                    [
                        ("product_id", "=", self.product_id.id),
                        ("picking_code", "=", "outgoing"),
                        ("state", "=", "confirmed"),
                    ]
                )
                product_moves.mapped("picking_id").write(
                    {"unknown_date": unknown_date_incoming}
                )
        # end
        return res

    def _get_new_picking_values(self):
        vals = super(StockMove, self)._get_new_picking_values()
        notes = [note for note in self.mapped("sale_line_id.order_id.note") if note]
        vals["note"] = ", ".join(notes)
        return vals
