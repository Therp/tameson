###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    email_signature = fields.Html(translate=True)
