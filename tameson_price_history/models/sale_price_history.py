# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _, tools
from odoo.exceptions import UserError, ValidationError


class SalePriceHistory(models.Model):
    _name = "sale.price.history"
    _description = "Sales Price History"

    _rec_name = "product_tmpl_id"
    _order = "date DESC"

    product_tmpl_id = fields.Many2one(
        string="Product", comodel_name="product.template", ondelete="cascade"
    )
    sale_price = fields.Float()
    date = fields.Date(
        string="Date",
        default=fields.Date.context_today,
    )


class ReportSPH(models.Model):
    _name = "report.sale.price.history"
    _auto = False

    product_tmpl_id = fields.Many2one(
        string="Product", comodel_name="product.template", ondelete="cascade"
    )
    sale_price = fields.Float()
    date = fields.Date(
        string="Date",
        default=fields.Date.context_today,
    )

    def init(self):
        tools.drop_view_if_exists(self._cr, "report_sale_price_history")
        query = """
CREATE or REPLACE VIEW report_sale_price_history AS (
with main as (
	select dt::date date, pt.id product_tmpl_id
	from generate_series((select min(date) from sale_price_history), (select max(date) from sale_price_history), '7 day'::interval) dt, 
	product_template pt 
	where pt.id in (select distinct product_tmpl_id from sale_price_history)
	order by dt DESC, pt.id asc
)
select row_number() over (order by main.date, main.product_tmpl_id) id, main.*, 
		(select sph.sale_price from sale_price_history sph
		 where sph.date <= main.date and main.product_tmpl_id = sph.product_tmpl_id
		 limit 1
			   )
from main)"""
        self.env.cr.execute(query)


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

    @api.model_create_multi
    def create(self, vals_list):
        records = super(ProductTemplate, self).create(vals_list)
        records.record_price_history()
        return records

    def write(self, vals):
        res = super(ProductTemplate, self).write(vals)
        if "list_price" in vals:
            self.record_price_history()
        return res

    def record_price_history(self):
        for pt in self:
            pt.write({"sale_price_ids": [(0, 0, {"sale_price": self.list_price})]})
