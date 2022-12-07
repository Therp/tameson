
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_is_zero, float_compare
from odoo.tools.profiler import profile

import json

def get_qty(data, delay):
    delays = []
    for item in data:
        if item['delay'] <= delay:
            stock = item['stock'] + item['max']
        else:
            stock = item['stock']
        delays.append(stock / item['bom_line_qty']) 
    return min(delays or [0])

class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    def set_bom_sale_price(self):
        sale_n = 5000
        cost_n = 10
        boms = self.filtered(lambda b: not float_is_zero(b.product_tmpl_id.pack_factor, precision_digits=3))
        for pos in range(0, len(boms), sale_n):
            boms[pos:pos+sale_n].with_delay().set_bom_sale_price_job()
        # for pos in range(0, len(self), cost_n):
        #     self[pos:pos+cost_n].with_delay().set_bom_cost_price_job()
        
    def set_bom_sale_price_job(self):
        self.env.cr.execute('''select default_code, list_price from product_template
where default_code in (SELECT unnest(string_to_array(additional_cost, ',')) AS sku
FROM (select distinct additional_cost from product_template) as ac)''')
        add_prices = dict(self.env.cr.fetchall())
        for bom in self:
            component_price = sum(bom.bom_line_ids.mapped(lambda l: l.product_id.list_price * l.product_qty))
            if not float_is_zero(bom.product_qty, precision_digits=3):
                add_price = 0
                additional_costs = bom.product_tmpl_id.additional_cost or ''
                for sku in additional_costs.split(','):
                    add_price += add_prices.get(sku, 0)
                price = ((component_price * bom.product_tmpl_id.pack_factor) / bom.product_qty) + add_price
                if float_compare(bom.product_tmpl_id.list_price, price, precision_digits=2) != 0:
                    bom.product_tmpl_id.write({'list_price': price})

    @profile
    def set_bom_cost_price_job(self):
        self.env.cr.execute('''select default_code, id from product_template
where default_code in (SELECT unnest(string_to_array(additional_cost, ',')) AS sku
FROM (select distinct additional_cost from product_template) as ac)''')
        add_prices = dict(self.env.cr.fetchall())
        boms = self.search([]).filtered(lambda b: b.product_tmpl_id.active)
        for bom in boms:
            product_tmpl_id = bom.product_tmpl_id
            product = product_tmpl_id.product_variant_id
            add_price = 0
            additional_costs = bom.product_tmpl_id.additional_cost or ''
            for sku in additional_costs.split(','):
                add_price += self.env["product.template"].browse(add_prices.get(sku, False)).standard_price
            account = product_tmpl_id.property_account_expense_id.id or product_tmpl_id.categ_id.property_account_expense_categ_id.id
            price = product._compute_bom_price(bom) + add_price
            product._change_standard_price(price, account)

        
    def set_bom_lead(self):
        for bom in self.filtered(lambda bom: bom.bom_line_ids):
            data = bom.bom_line_ids.mapped(lambda l: {
                    'stock': l.product_id.minimal_qty_available_stored,
                    'delay': l.product_id.seller_ids[:1].delay, 
                    'bom_line_qty': l.product_qty, 
                    'max': l.product_id.max_qty_order
                })
            delay = max([0 if not float_is_zero(item['stock'], precision_digits=1) else item['delay'] for item in data])
            delay_list = list(sorted(set([item['delay'] for item in data])))
            delay_list.insert(0, 0)
            delay_array = []
            for lead in delay_list:
                max_qty = get_qty(data, lead)
                if max_qty > 0:
                    delay_array.append({'lead_time': lead+1, 'max_qty': max_qty})
            max_qty_order = get_qty(data, delay)
            bom.product_tmpl_id.write({
                't_customer_lead_time': delay + 1,
                'max_qty_order': max_qty_order,
                'max_qty_order_array': json.dumps(delay_array),
            })
