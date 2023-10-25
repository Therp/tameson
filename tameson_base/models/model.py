###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import fields, models


class IrModel(models.Model):
    _inherit = "ir.model"

    help_text = fields.Html()
