# Copyright 2020 Therp BV <https://therp.nl>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models


class ProductCategory(models.Model):
    _inherit = 'product.category'


    procured_purchase_grouping = fields.Selection(
        selection_add=[('line_specific' ,
                        'No line grouping for specific suppliers.')]
    )

