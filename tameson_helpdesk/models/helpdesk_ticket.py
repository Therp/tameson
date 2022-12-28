
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError



class ModelName(models.Model):
    _name = 'helpdesk.ticket'
    _inherit = ['helpdesk.ticket', 'set.help.mixin']

    any_non_returnable = fields.Boolean(related='sale_order_id.any_non_returnable')
    non_returnable_skus = fields.Char(related='sale_order_id.non_returnable_skus')

    def action_reship(self):
        view = self.env.ref('tameson_helpdesk.view_stock_picking_reship')
        action = self.env.ref('stock.act_stock_return_picking').read()[0]
        action.update({
            'views': [(view.id, 'form')],
            'name': "Reship Delivery",
            'display_name': "Reship Delivery",
        })
        return action
