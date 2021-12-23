# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError



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