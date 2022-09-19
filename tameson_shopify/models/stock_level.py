
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ShopifyStockLevel(models.TransientModel):
    _name = 'shopify.stock.level'
    _description = 'Shopify Stock Level'

    _rec_name = 'name'
    _order = 'name ASC'

    name = fields.Char(string='SKU', required=True,)
    inventory_item_id = fields.Char(required=True)
    variant_id = fields.Char(required=True)
    shopify_tmpl_id = fields.Char(required=True)
    available = fields.Float()
    
    @api.model_create_multi
    def create(self, vals_list):
        result = super(ShopifyStockLevel, self).create(vals_list)    
        return result
    