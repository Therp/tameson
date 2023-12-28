###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        if self.signature:
            txs = self.transaction_ids.filtered(
                lambda tx: tx.state in ("draft", "pending")
            )
            txs.unlink()
        return super().action_confirm()
