###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    signature = fields.Html(translate=True)
