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
