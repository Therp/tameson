
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_is_zero

class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    def set_bom_sale_price(self):
        n = 5000
        boms = self.filtered(lambda b: not float_is_zero(b.product_tmpl_id.pack_factor, precision_digits=3))
        for pos in range(0, len(boms), n):
            boms[pos:pos+n].with_delay().set_bom_sale_price_job()
        
    def set_bom_sale_price_job(self):
        for bom in self:
            component_price = sum(bom.bom_line_ids.mapped(lambda l: l.product_id.lst_price * l.product_qty))
            if not float_is_zero(bom.product_qty, precision_digits=3):
                bom.product_tmpl_id.lst_price = (component_price * bom.product_tmpl_id.pack_factor) / bom.product_qty
