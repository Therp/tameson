# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from itertools import product
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def action_open_vendor_sku(self):
        url = self.get_vendor_url()
        if url:
            return {
                "type": "ir.actions.act_url",
                "url": url,
                "target": "new",
            }

    def get_vendor_url(self):
        url = ''
        seller = self.seller_ids[:1]
        if seller.name.id == 12: ## 12 for landefeld
            sku = seller.product_code.replace(' ', '+')
            url = 'https://www.landefeld.de/cgi/main.cgi?DISPLAY=suche&filter_suche_artikelmenge=&filter_suche_suchstring=%s' % sku
        if seller.name.id == 12:
            url = 'https://www.burkert.nl/en/products/%d' % seller.product_code
        return url