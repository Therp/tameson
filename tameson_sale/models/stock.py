
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError



class StockPicking(models.Model):
    _inherit = 'stock.picking'

    
    source_so_id = fields.Many2one(comodel_name='sale.order', compute='_get_source_so')

    @api.depends('origin')
    def _get_source_so(self):
        for record in self:
            record.source_so_id = self.env['sale.order'].search([('name','=',record.origin)], limit=1)

    def get_commercial_price(self):
        return self.mapped('move_lines').get_commercial_price()

class StockMove(models.Model):
    _inherit = 'stock.move'
    
    def get_commercial_price(self):
        data = []
        for move in self:
            move_product = move.product_id
            commercial_price = 0
            currency = self.env.user.company_id.currency_id.name
            if move.sale_line_id:
                sale_line = move.sale_line_id
                sale_product = sale_line.product_id
                bom_kit = self.env['mrp.bom']._bom_find(product=sale_product, bom_type='phantom')
                if bom_kit:
                    total_qty = sum(bom_kit.bom_line_ids.mapped('product_qty'))
                    commercial_price = (sale_line.price_total / sale_line.product_uom_qty) * move.product_uom_qty / total_qty
                else:
                    commercial_price = (sale_line.price_total / sale_line.product_uom_qty) * move.product_uom_qty
                currency = sale_line.currency_id.name
            if not commercial_price:
                commercial_price = move.product_id.list_price
            data.append({
                'picking_id': move.picking_id.id,
                'move_id': move.id,
                'price': commercial_price,
                'currency': currency
            })
        return data