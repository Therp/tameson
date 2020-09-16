
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

@api.model
def _lang_get(self):
    return self.env['res.lang'].get_installed()

class ResCountry(models.Model):
    _inherit = 'res.country'

    select_shipment_id = fields.Many2one(string='Default Shipment',comodel_name='delivery.carrier',ondelete='restrict',)
    select_lang = fields.Selection(_lang_get, string='Default Language',)
    

