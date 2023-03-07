###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models


class PortalWizardUser(models.TransientModel):
    _inherit = "portal.wizard.user"

    def _send_email(self):
        return
