###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import fields, models


class ResCountry(models.Model):
    _inherit = "res.country"

    iso3 = fields.Char(string="ISO 3 Code", size=3)
