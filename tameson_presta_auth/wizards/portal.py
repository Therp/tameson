
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class PortalWizardUser(models.TransientModel):
    _inherit = 'portal.wizard.user'

    def _send_email(self):
        if self.env.context.get('send_mail', True):
            return super(PortalWizardUser, self)._send_email()
