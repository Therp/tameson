###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import fields, models


class ModelName(models.Model):
    _name = "helpdesk.ticket"
    _inherit = ["helpdesk.ticket", "set.help.mixin"]

    any_non_returnable = fields.Boolean(related="sale_order_id.any_non_returnable")
    non_returnable_skus = fields.Char(related="sale_order_id.non_returnable_skus")
    restock_fee_limit_warning = fields.Boolean(compute="_get_restock_fee_limit")
    restock_fee_limit = fields.Char(compute="_get_restock_fee_limit")

    def _get_restock_fee_limit(self):
        restock_fee_limit = (
            self.env["ir.config_parameter"].sudo().get_param("restock_fee_limit", 0)
        )
        limit = float(restock_fee_limit)
        for record in self:
            if (
                limit > 1
                and record.sale_order_id
                and record.sale_order_id.amount_total >= limit
            ):
                record.restock_fee_limit_warning = True
                record.restock_fee_limit = restock_fee_limit
            else:
                record.restock_fee_limit_warning = False
                record.restock_fee_limit = ""

    def action_reship(self):
        view = self.env.ref("tameson_helpdesk.view_stock_picking_reship")
        action = self.env.ref("stock.act_stock_return_picking").read()[0]
        action.update(
            {
                "views": [(view.id, "form")],
                "name": "Reship Delivery",
                "display_name": "Reship Delivery",
            }
        )
        return action
