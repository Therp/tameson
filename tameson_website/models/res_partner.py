###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def can_edit_vat(self):
        if not (self.vat or self.parent_id):
            return True
        else:
            return super(ResPartner, self).can_edit_vat()
