###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models


class Workflow(models.Model):
    _inherit = "automatic.workflow.job"

    def _prepare_dict_account_payment(self, invoice):
        res = super()._prepare_dict_account_payment(invoice)
        res["currency_id"] = invoice.currency_id.id
        res["ref"] = invoice.payment_reference
        return res
