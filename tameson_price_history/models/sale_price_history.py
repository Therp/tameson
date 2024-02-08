###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import api, fields, models
from odoo.tools import float_compare


class SalePriceHistory(models.Model):
    _name = "sale.price.history"
    _description = "Sales Price History"

    _rec_name = "product_tmpl_id"
    _order = "date DESC"

    product_tmpl_id = fields.Many2one(
        string="Product", comodel_name="product.template", ondelete="cascade"
    )
    categ_id = fields.Many2one(
        string="Category",
        comodel_name="product.category",
        ondelete="restrict",
        related="product_tmpl_id.categ_id",
    )
    sale_price = fields.Float()
    date = fields.Date(
        string="Date",
        default=fields.Date.context_today,
    )


class ProductTemplate(models.Model):
    _inherit = "product.template"

    sale_price_ids = fields.One2many(
        comodel_name="sale.price.history",
        inverse_name="product_tmpl_id",
    )
    supplier_price_ids = fields.One2many(
        comodel_name="supplier.price.history",
        inverse_name="product_tmpl_id",
    )

    supplierinfo_list_price = fields.Float(
        string="Vendor List Price",
        compute="_compute_supplier_list_price",
        store=True,
    )

    @api.depends("seller_ids.partner_id", "seller_ids.list_price_eur")
    def _compute_supplier_list_price(self):
        for product in self:
            first_supplier = product.seller_ids.sorted()[:1]
            if first_supplier:
                product.supplierinfo_list_price = first_supplier.list_price_eur

    @api.model_create_multi
    def create(self, vals_list):
        records = super(ProductTemplate, self).create(vals_list)
        records.record_price_history()
        return records

    def write(self, vals):
        old_price = self.list_price
        res = super(ProductTemplate, self).write(vals)
        if "list_price" in vals:
            if float_compare(old_price, self.list_price, precision_digits=2):
                self.record_price_history()
        return res

    def record_price_history(self):
        for pt in self:
            pt.write({"sale_price_ids": [(0, 0, {"sale_price": self.list_price})]})
