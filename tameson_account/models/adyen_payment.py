
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


import logging
_logger = logging.getLogger(__name__)


class Payment(models.Model):
    _inherit = 'payment.acquirer'

    # totally replace existing function from payment_adyen module, inheritance chain breaks here
    def _adyen_form_validate(self, data):
        status = data.get('authResult', 'PENDING')
        if status == 'AUTHORISED':
            self.write({'acquirer_reference': data.get('pspReference')})
            self._set_transaction_done()
            return True
        elif status == 'PENDING':
            self.write({'acquirer_reference': data.get('pspReference')})
            self._set_transaction_pending()
            return True
        else:
            error = 'Adyen feedback: Authorisation: %s' % status
            _logger.info(error)
            self.write({'state_message': error})
            self._set_transaction_cancel()
            return False


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _invoice_sale_orders(self):
        if self.env['ir.config_parameter'].sudo().get_param('sale.automatic_invoice'):
            for trans in self.filtered(lambda t: t.sale_order_ids):
                ctx_company = {'company_id': trans.acquirer_id.company_id.id,
                               'force_company': trans.acquirer_id.company_id.id}
                trans = trans.with_context(**ctx_company)
                trans.sale_order_ids._force_lines_to_invoice_policy_order()
                invoices = self.env['account.move']
                # look for invoice status before trying to create new invoice
                # to fix error for online payment with orders already invoiced
                for so in trans.sale_order_ids:
                    if so.invoice_status != 'invoiced':
                        so._create_invoices()
                    invoices |= so.invoice_ids.filtered(lambda i: i.state != 'cancel')                
                # invoices = trans.sale_order_ids._create_invoices()
                trans.invoice_ids = [(6, 0, invoices.ids)]
