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
        total_price = json.loads(order_data_queue_line.order_data).get('order',{}).get('total_price',0)
        if float_compare(float(total_price), order_id.amount_total, precision_digits=2) != 0:
            raise UserError("Total amount missmatch %.2f %.2f")
        return order_id

