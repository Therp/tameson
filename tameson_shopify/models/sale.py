# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

import json
from odoo import models, fields, api, _, SUPERUSER_ID
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare
from datetime import datetime


def filter_orders(order):
    difference = abs(order.shopify_total_price - order.amount_total)
    return float_compare(difference, 0.05, precision_digits=2) != 1

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    
    shopify_total_price = fields.Float(readonly=True)

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
            'origin': "%s - %s" % (instance.name, name)
        })
        return vals
    
    def import_shopify_orders(self, order_data_queue_line, log_book_id):
        order_id = super(SaleOrder, self).import_shopify_orders(order_data_queue_line, log_book_id)
        total_price = float(json.loads(order_data_queue_line.order_data).get('order',{}).get('total_price',0))
        if order_id:
            order_id.shopify_total_price = total_price
        difference = abs(total_price - order_id.amount_total)
        if order_id and float_compare(difference, 0.05, precision_digits=2) == 1:
            msg = "Total amount missmatch shopify: %.2f odoo: %.2f" % (total_price, order_id.amount_total)
            order_id.activity_schedule('mail.mail_activity_data_warning', datetime.today().date(),
                note=msg, user_id=order_id.user_id.id or SUPERUSER_ID)
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

    def process_orders_and_invoices_ept(self):
        order = self.filtered(lambda o: filter_orders(o))
        return super(SaleOrder, order).process_orders_and_invoices_ept()
