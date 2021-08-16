
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
