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
        for rec in records:
            rec.record_price_history()
        return records

    def write(self, vals_list):
        values = vals_list if isinstance(vals_list, list) else [vals_list]
        for pt, vals in zip(self, values):
            if "list_price" in vals:
                old_price = pt.list_price
                new_price = vals["list_price"]
                if float_compare(old_price, new_price, precision_digits=2):
                    pt.record_price_history(new_price)
        return super(ProductTemplate, self).write(vals_list)

    def record_price_history(self, new_price=None):
        price = new_price or self.list_price
        self.write({"sale_price_ids": [(0, 0, {"sale_price": price})]})
