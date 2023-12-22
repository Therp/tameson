###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models


class Product(models.Model):
    _inherit = "product.product"

    def _compute_product_website_url(self):
        for product in self:
            product.website_url = "#"
