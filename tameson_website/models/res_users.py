###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models


class ResUsers(models.Model):
    _inherit = "res.users"

    def reset_password(self, login):
        login = login.lower()
        return super().reset_password(login)
