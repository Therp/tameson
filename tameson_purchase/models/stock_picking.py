# Copyright 2020 Therp BV <https://therp.nl>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import api, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def write(self, values):
        # on every picking modification , we reassociate the picking/IN of
        # the purchase order with it's corresponding picking/OUT of sales order
        # when it exists (non aggregated dale order lines)
        res = super(StockPicking, self).write(values)
        for this in self:
            for origin in this.origin.split(","):
                purchase = self.env["purchase.order"].search([("name", "=", origin)])
                if purchase:
                    purchase.find_and_refresh_picking_in_out_associations()
                    break
        return res

    @api.model
    def created(self, values):
        res = super(StockPicking, self).create(values)
        for origin in self.origin.split(","):
            purchase = self.env["purchase.order"].search([("name", "=", origin)])
            if purchase:
                purchase.find_and_refresh_picking_in_out_associations()
                break
        return res

    def do_print_picking_origin_so(self):
        return self.env.ref(
            "tameson_purchase.action_report_picking_origin_so"
        ).report_action(self.mapped("move_lines.origin_so_picking_ids"))
