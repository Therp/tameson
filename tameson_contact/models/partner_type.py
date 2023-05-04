###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import fields, models


class PartnerType(models.Model):
    _name = "tameson.partner.type"
    _description = "Partner Type"

    _rec_name = "name"
    _order = "name ASC"

    name = fields.Char(string="Name", required=True, copy=False)
