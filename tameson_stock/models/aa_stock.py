###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

import json

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AAStock(models.TransientModel):
    _name = "aa.stock"
    _description = "AA Stock"

    sku = fields.Char()
    stock = fields.Float()

    @api.model_create_multi
    def create(self, vals_list):
        self.search([]).unlink()
        super(AAStock, self).create(vals_list)

    def get_data(self, whs=False):
        aa_data = []
        if not whs:
            whs = self.env["stock.warehouse"].search(
                [
                    ("aa_api", "!=", False),
                    ("aa_username", "!=", False),
                    ("aa_password", "!=", False),
                ]
            )
        for wh in whs:
            try:
                token_response = requests.post(
                    "%s/token" % wh.aa_api,
                    data={
                        "grant_type": "password",
                        "username": wh.aa_username,
                        "password": wh.aa_password,
                    },
                )
                token = json.loads(token_response.text)["access_token"]
                data_response = requests.get(
                    "%s/stock/bulk/true" % wh.aa_api,
                    headers={"Authorization": "Bearer %s" % token},
                )
                data = json.loads(data_response.text)
            except Exception as e:
                raise UserError(str(e)) from e
            vals = [
                {"sku": result["sku"], "stock": result["physicalStock"]}
                for result in data["result"]
            ]
            self.create(vals)
            locations = self.env["stock.location"].search(
                [("id", "child_of", wh.lot_stock_id.id)]
            )
            query = """
WITH onhand_query AS (
    SELECT
        sum(quantity) quantity,
        pt.default_code sku
    FROM
        stock_quant sq
        LEFT JOIN stock_location sl ON sl.id = sq.location_id
        LEFT JOIN product_product pp on pp.id = sq.product_id
        LEFT JOIN product_template pt on pt.id = pp.product_tmpl_id
    WHERE
        sl.usage = 'internal' AND
        sl.id in (%s)
    GROUP BY
        pt.default_code
)
SELECT
    pt.id product_id,
    aas.sku sku,
    pt.name ptname,
    aas.stock aa_quantity,
    coalesce(oh.quantity, 0) odoo_quantity
FROM
    aa_stock aas
    LEFT JOIN onhand_query oh on oh.sku = aas.sku
    LEFT JOIN product_template pt on pt.default_code = aas.sku
WHERE
    coalesce(oh.quantity, 0) != aas.stock
""" % ",".join(
                map(str, locations.ids)
            )
            self.env.cr.execute(query)
            aa_data += self.env.cr.fetchall()
        return aa_data


class AAStockCompare(models.Model):
    _name = "aa.stock.comparison"
    _description = "AA Stock"

    product_id = fields.Many2one(
        comodel_name="product.template",
        ondelete="set null",
    )
    aa_stock = fields.Float()
    odoo_stock = fields.Float()
    difference = fields.Float(compute="get_difference", store=True)

    @api.depends("aa_stock", "odoo_stock")
    def get_difference(self):
        for record in self:
            record.difference = record.aa_stock - record.odoo_stock

    @api.model_create_multi
    def create(self, vals_list):
        result = super(AAStockCompare, self).create(vals_list)
        return result

    def action_open_product(self):
        return {
            "name": _("Product"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "product.template",
            "res_id": self.product_id.id,
            "target": "new",
        }

    @api.model
    def read_grid(
        self,
        row_fields,
        col_field,
        cell_field,
        domain=None,
        range=None,
        readonly_field=None,
        orderby=None,
    ):
        if not orderby:
            orderby = "create_date"
        read_grid = super(AAStockCompare, self).read_grid(
            row_fields,
            col_field,
            cell_field,
            domain=domain,
            range=range,
            readonly_field=readonly_field,
            orderby=orderby,
        )
        return read_grid


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    aa_username = fields.Char()
    aa_api = fields.Char()
    aa_password = fields.Char(password=True)

    def compare_aa_stock(self):
        if not self:
            self = self.search(
                [
                    ("aa_api", "!=", False),
                    ("aa_username", "!=", False),
                    ("aa_password", "!=", False),
                ]
            )
        for wh in self:
            data = self.env["aa.stock"].get_data(wh)
            vals_list = [
                {"product_id": val[0], "aa_stock": val[3], "odoo_stock": val[4]}
                for val in data
            ]
            comparison = self.env["aa.stock.comparison"]
            comparison.create(vals_list)
