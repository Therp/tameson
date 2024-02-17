###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    email = fields.Char(translate=True, related=False)
    phone = fields.Char(translate=True, related=False)
    mobile = fields.Char(translate=True, related=False)
    website = fields.Char(store=True, translate=True, related=False)
