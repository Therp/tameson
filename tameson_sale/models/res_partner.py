
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError



class ResPartnet(models.Model):
    _inherit = 'res.partner'

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        for partner in partners:
            if not partner.lang:
                partner.lang = partner.country_id.select_lang or 'en_US'
            if not partner.parent_id:
                partner.property_product_pricelist = partner.country_id.select_pricelist_id
        return partners