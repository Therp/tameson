# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

import json
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    
    def prepare_shopify_order_vals(self, instance, partner, shipping_address,
                                   invoice_address, order_response, payment_gateway,
                                   workflow):
        vals = super(SaleOrder, self).prepare_shopify_order_vals(instance, partner, shipping_address,
                                   invoice_address, order_response, payment_gateway,
                                   workflow)
        po_ref = order_response.get('metafields', {}).get('po_reference', False)
        name = order_response.get("name")
        if po_ref:
            vals.update({
                'client_order_ref': "%s - %s" % (po_ref, name)
            })
        vals.update({
            'origin': "%s - %s" % (instance.shopify_host, name)
        })
        return vals
    
    def import_shopify_orders(self, order_data_queue_line, log_book_id):
        order_id = super(SaleOrder, self).import_shopify_orders(order_data_queue_line, log_book_id)
        total_price = float(json.loads(order_data_queue_line.order_data).get('order',{}).get('total_price',0))
        if order_id and float_compare(total_price, order_id.amount_total, precision_digits=2) != 0:
            raise UserError("Total amount missmatch shopify: %.2f odoo: %.2f" % (total_price, order_id.amount_total))
        return order_id

    def shopify_create_sale_order_line(self, line, product, quantity,
                                       product_name, order_id,
                                       price, order_response, is_shipping=False,
                                       previous_line=False,
                                       is_discount=False):
        line_id  = super(SaleOrder, self).shopify_create_sale_order_line(line, product, quantity,
                                       product_name, order_id,
                                       price, order_response, is_shipping,
                                       previous_line, is_discount)
        tax =  sum([float(l['rate']) for l in line['tax_lines']])
        line_id.price_unit = line_id.price_unit / (1 + tax)
        line_id.with_context(round=False)._compute_amount()
        return line_id