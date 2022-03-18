# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class SupplierPriceHistory(models.Model):
    _name = "supplier.price.history"
    _description = "Supplier Price History"

    _rec_name = "product_tmpl_id"
    _order = "date DESC"

    product_tmpl_id = fields.Many2one(
        string="Product", comodel_name="product.template", ondelete="cascade"
    )
    supplier_id = fields.Many2one(
        comodel_name="res.partner",
        ondelete="restrict",
    )
    supplier_price = fields.Float()
    supplier_price_orig = fields.Float()
    supplier_currency_id = fields.Many2one(
        comodel_name="res.currency",
        ondelete="restrict",
    )
    supplier_code = fields.Char()
    date = fields.Date(
        string="Date",
        default=fields.Date.context_today,
    )


class ProductSupplierinfo(models.Model):
    _inherit = "product.supplierinfo"

    @api.model
    def create(self, vals_list):
        records = super(ProductSupplierinfo, self).create(vals_list)
        records.record_price_history()
        return records

    def write(self, vals):
        res = super(ProductSupplierinfo, self).write(vals)
        if "price" in vals or "name" in vals:
            self.record_price_history()
        return res

    def record_price_history(self):
        for ps in self:
            price_orig = ps.price
            ccur= self.env.user.company_id.currency_id
            price = ps.currency_id._convert(
                    price_orig, ccur,
                    self.env.user.company_id, fields.Date.today()
                ) if ps.currency_id.id != ccur.id else price_orig
            
            ps.product_tmpl_id.write(
                {
                    "supplier_price_ids": [
                        (
                            0,
                            0,
                            {
                                "supplier_id": ps.name.id,
                                "supplier_price": price,
                                "supplier_price_orig": price_orig,
                                "supplier_currency_id": ps.currency_id.id,
                                "supplier_code": ps.product_code,
                            },
                        )
                    ]
                }
            )
