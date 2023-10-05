###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_product_supplier = fields.Boolean()
    average_payment_days = fields.Float(compute="get_average_payment_days")

    def get_average_payment_days(self):
        for partner in self:
            all_child = self.with_context(active_test=False).search(
                [("id", "child_of", partner.ids)]
            )
            payments = (
                self.env["account.payment"]
                .sudo()
                .search(
                    [
                        ("partner_id", "in", all_child.ids),
                        ("payment_type", "=", "inbound"),
                    ]
                )
            )
            days = []
            for payment in payments:
                for invoice in payment.reconciled_invoice_ids:
                    days.append((payment.payment_date - invoice.date).days)
            if days:
                partner.average_payment_days = sum(days) / len(days)
            else:
                partner.average_payment_days = 0
