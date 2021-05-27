
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