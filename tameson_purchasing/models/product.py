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

    is_vendor_url_available = fields.Boolean(compute="get_vendor_url_available")

    def get_vendor_url_available(self):
        for pt in self:
            seller = pt.seller_ids[:1]
            if seller.name.id in (12, 24990):
                pt.is_vendor_url_available = True
            else:
                pt.is_vendor_url_available = False

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
        if seller.name.id == 24990: ## 24990 for burkert
            url = 'https://www.burkert.nl/en/products/%s' % seller.product_code
        return url