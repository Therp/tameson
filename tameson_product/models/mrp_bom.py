
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_is_zero

def get_qty(item, delay):
    return (item['stock'] + (item['max'] * (1 if item['delay'] <= delay else 0))) / item['bom_line_qty']

class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    def set_bom_sale_price(self):
        n = 5000
        boms = self.filtered(lambda b: not float_is_zero(b.product_tmpl_id.pack_factor, precision_digits=3))
        for pos in range(0, len(boms), n):
            boms[pos:pos+n].with_delay().set_bom_sale_price_job()
        all_boms = self.search([])
        for pos in range(0, len(all_boms), n):
            all_boms[pos:pos+n].with_delay().set_bom_lead()
        
    def set_bom_sale_price_job(self):
        for bom in self:
            component_price = sum(bom.bom_line_ids.mapped(lambda l: l.product_id.lst_price * l.product_qty))
            if not float_is_zero(bom.product_qty, precision_digits=3):
                bom.product_tmpl_id.lst_price = (component_price * bom.product_tmpl_id.pack_factor) / bom.product_qty

    def set_bom_lead(self):
        for bom in self.filtered(lambda bom: bom.bom_line_ids):
            data = bom.bom_line_ids.mapped(lambda l: {
                    'stock': l.product_id.minimal_qty_available_stored,
                    'delay': l.product_id.seller_ids[:1].delay, 
                    'bom_line_qty': l.product_qty, 
                    'max': l.product_id.max_qty_order
                })
            delay = max([0 if not float_is_zero(item['stock'], precision_digits=1) else item['delay'] for item in data])
            max_qty_order = max([get_qty(item, delay) for item in data])

            bom.product_tmpl_id.write({
                't_customer_lead_time': delay + 1,
                'max_qty_order': max_qty_order
            })
