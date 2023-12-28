# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class PaymentProvider(models.Model):
    _inherit = "payment.provider"

    custom_mode = fields.Selection(
        selection_add=[("tameson", "Tameson")],
        ondelete={
            "tameson": "set null",
        },
    )

    def _get_compatible_providers(self, company_id, partner_id, *args, **kwargs):
        providers = super()._get_compatible_providers(
            company_id, partner_id, *args, **kwargs
        )
        partner = self.env["res.partner"].browse(partner_id)
        if not partner.property_payment_term_id.t_invoice_delivered_quantities:
            providers = providers.filtered(
                lambda pr: not (pr.code == "custom" and pr.custom_mode == "tameson")
            )
        return providers


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    def _get_specific_rendering_values(self, processing_values):
        if self.provider_code == "custom" and self.provider_id.custom_mode == "tameson":
            return {
                "api_url": "/payment/custom/tameson_process",
                "reference": self.reference,
            }
        return super()._get_specific_rendering_values(processing_values)

    def _set_pending(self, state_message=None):
        """Override of `payment` to send the quotations automatically.

        :param str state_message: The reason for which the transaction is set in 'pending' state.
        :return: updated transactions.
        :rtype: `payment.transaction` recordset.
        """
        txs_to_process = super()._set_pending(state_message=state_message)

        for (
            tx
        ) in txs_to_process:  # Consider only transactions that are indeed set pending.
            sales_orders = tx.sale_order_ids.filtered(
                lambda so: so.state in ["draft", "sent"]
            )
            sales_orders.filtered(lambda so: so.state == "draft").with_context(
                tracking_disable=True
            ).action_quotation_sent()

            if tx.provider_id.code == "custom":
                for so in tx.sale_order_ids:
                    so.reference = tx._compute_sale_order_reference(so)
            # send order confirmation mail.
            # sales_orders._send_order_confirmation_mail()

        return txs_to_process
