###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo.http import request, route

from odoo.addons.payment.controllers.portal import WebsitePayment


class WebsitePayment(WebsitePayment):
    @route(["/my/payment_method"], type="http", auth="user", website=True)
    def payment_method(self, **kwargs):
        acquirers = list(
            request.env["payment.acquirer"].search(
                [
                    ("state", "in", ["enabled", "test"]),
                    ("registration_view_template_id", "!=", False),
                    ("payment_flow", "=", "s2s"),
                    ("company_id", "=", request.env.company.id),
                    ("provider", "!=", "manual"),
                ]
            )
        )
        partner = request.env.user.partner_id
        payment_tokens = partner.payment_token_ids
        payment_tokens |= partner.commercial_partner_id.sudo().payment_token_ids
        return_url = request.params.get("redirect", "/my/payment_method")
        values = {
            "pms": payment_tokens,
            "acquirers": acquirers,
            "error_message": [kwargs["error"]] if kwargs.get("error") else False,
            "return_url": return_url,
            "bootstrap_formatting": True,
            "partner_id": partner.id,
        }
        return request.render("payment.pay_methods", values)
