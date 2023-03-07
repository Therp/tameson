###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    source_po_id = fields.Many2one(
        comodel_name="purchase.order", compute="_get_source_po"
    )

    @api.depends("origin")
    def _get_source_po(self):
        for record in self:
            record.source_po_id = self.env["purchase.order"].search(
                [("name", "=", record.origin)], limit=1
            )

    def do_print_picking_origin_so(self):
        self.mapped("move_lines.origin_so_picking_ids")
        return self.env.ref("stock.action_report_delivery").report_action(
            self.mapped("move_lines.origin_so_picking_ids")
        )


class StockMove(models.Model):
    _inherit = "stock.move"

    origin_so_picking_ids = fields.Many2many(
        "stock.picking", compute="_get_so_pickings"
    )

    def _get_so_pickings(self):
        for move in self:
            move.origin_so_picking_ids = move.move_dest_ids.mapped("picking_id")
