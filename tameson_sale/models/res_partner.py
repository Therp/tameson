###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        for partner in partners:
            if not partner.lang:
                partner.lang = partner.country_id.select_lang or "en_US"
            if not partner.parent_id:
                partner.property_product_pricelist = (
                    partner.country_id.select_pricelist_id
                )
        return partners

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        res.update(
            {
                "lang": False,
            }
        )
        return res

    # @api.onchange("property_payment_term_id")
    # def onchange_payment_term(self):
    #     limit = self.property_payment_term_id.t_invoice_delivered_quantities
    #     self.update(
    #         {
    #             "risk_sale_order_include": limit,
    #             "risk_invoice_draft_include": limit,
    #             "risk_invoice_open_include": limit,
    #             "risk_invoice_unpaid_include": limit,
    #         }
    #     )


class AccountPaymentTerm(models.Model):
    _inherit = "account.payment.term"

    workflow_process_id = fields.Many2one(
        string="Workflow",
        comodel_name="sale.workflow.process",
        ondelete="restrict",
    )

    t_invoice_delivered_quantities = fields.Boolean(
        string="Invoice delivered quantities"
    )
