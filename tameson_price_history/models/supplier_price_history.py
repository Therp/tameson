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
    categ_id = fields.Many2one(
        string='Category',
        comodel_name='product.category',
        ondelete='restrict',
        related='product_tmpl_id.categ_id'
    )
    @api.model
    def create(self, vals_list):
        currency_id = vals_list.get("supplier_currency_id", False)
        if not currency_id:
            currency_id = 1
            vals_list["supplier_currency_id"] = 1
        if currency_id == 1:
            vals_list["supplier_price"] = vals_list["supplier_price_orig"]
        else:
            currency = self.env["res.currency"].browse(currency_id)
            price = currency._convert(
                vals_list["supplier_price_orig"],
                self.env.user.company_id.currency_id,
                self.env.user.company_id,
                vals_list.get("date", False) or fields.Date.today(),
            )
            vals_list["supplier_price"] = price
        return super(SupplierPriceHistory, self).create(vals_list)

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
            ps.product_tmpl_id.write(
                {
                    "supplier_price_ids": [
                        (
                            0,
                            0,
                            {
                                "supplier_id": ps.name.id,
                                "supplier_price_orig": ps.price,
                                "supplier_currency_id": ps.currency_id.id,
                                "supplier_code": ps.product_code,
                            },
                        )
                    ]
                }
            )
