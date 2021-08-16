
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    
    source_po_id = fields.Many2one(comodel_name='purchase.order', compute='_get_source_po')

    @api.depends('origin')
    def _get_source_po(self):
        for record in self:
            record.source_po_id = self.env['purchase.order'].search([('name','=',record.origin)], limit=1)
