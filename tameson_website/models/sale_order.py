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

    def action_send_signature_remaining(self):
        if self.state == "sent":
            mail_template = self.env["mail.template"].search(
                [("name", "ilike", "Tameson: Signature remaining to confirm order")],
                limit=1,
            )
            if mail_template:
                self.with_context(force_send=True).message_post_with_template(
                    mail_template.id,
                    composition_mode="comment",
                    email_layout_xmlid="mail.mail_notification_layout_with_responsible_signature",
                )
            return 'Signature remaining email sent.'