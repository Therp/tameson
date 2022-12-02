
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError



class ResPartnet(models.Model):
    _inherit = 'res.partner'

    #On partner creation view, automatically change partner language to default language for partners country
    @api.onchange('country_id')
    def onchange_country_lang(self):
        if self.country_id.select_lang:
            self.lang = self.country_id.select_lang

    
    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        for partner in partners:
            if partner.parent_id:
                continue
            partner.property_product_pricelist = partner.country_id.select_pricelist_id
        return partner