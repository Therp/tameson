
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError



class StockPicking(models.Model):
    _inherit = 'stock.picking'

    t_aa_name = fields.Char('Active Ant Name', compute='_get_t_aa_name')
    t_aa_id = fields.Char('Active Ant ID', readonly=True)
    t_aa_track_url = fields.Char('Active Ant tracktraceUrl', readonly=True)
    source_so_id = fields.Many2one(comodel_name='sale.order', compute='_get_source_so')

    @api.depends('origin')
    def _get_source_so(self):
        for record in self:
            record.source_so_id = self.env['sale.order'].search([('name','=',record.origin)], limit=1)

    @api.depends('name', 'sale_id')
    def _get_t_aa_name(self):
        for record in self:
            record.t_aa_name = "%s - %s" % (record.sale_id.name, record.name)

class StockMove(models.Model):
    _inherit = 'stock.move'
    
    t_aa_comm_price = fields.Float('Commercial Price', compute='_get_commercial_price')
    t_aa_comm_taxrate = fields.Float('Tax Rate', compute='_get_commercial_price')
    
    @api.depends('sale_line_id')
    def _get_commercial_price(self):
        for move in self:
            commercial_price = 0
            if move.sale_line_id:
                sale_line = move.sale_line_id
                sale_product = sale_line.product_id
                bom_kit = self.env['mrp.bom']._bom_find(product=sale_product, bom_type='phantom')
                if bom_kit:
                    total_qty = sum(bom_kit.bom_line_ids.mapped('product_qty'))
                    commercial_price = (sale_line.price_total / sale_line.product_uom_qty) * move.product_uom_qty / total_qty
                else:
                    commercial_price = (sale_line.price_total / sale_line.product_uom_qty) * move.product_uom_qty
                tax_rate = move.sale_line_id.tax_id[:1].amount
            if not commercial_price:
                commercial_price = move.product_id.list_price
                tax_rate = 0
            move.t_aa_comm_price = commercial_price
            move.t_aa_comm_taxrate = tax_rate
