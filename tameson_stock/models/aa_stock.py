# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import requests, json


class AAStock(models.TransientModel):
    _name = 'aa.stock'
    _description = 'AA Stock'

    sku = fields.Char()
    stock = fields.Float()

    @api.model_create_multi
    def create(self, vals_list):
        self.search([]).unlink()
        super(AAStock, self).create(vals_list)

    def get_data(self):
        aa_data = []
        for wh in self.env['stock.warehouse'].search([('aa_username','!=',False),('aa_password','!=',False)]):
            try:
                token_response = requests.post("%s/token" % wh.aa_api,data={
                    "grant_type": "password",
                    "username": wh.aa_username,
                    "password": wh.aa_password
                })
                token = json.loads(token_response.text)['access_token']
                data_response = requests.get("%s/stock/bulk/true" % wh.aa_api, headers={'Authorization': 'Bearer %s' % token})
                data = json.loads(data_response.text)
            except Exception as e:
                raise UserError(str(e))
            vals = [{'sku': result['sku'], 'stock': result['stock']} for result in data['result']]
            self.create(vals)
            locations = self.env['stock.location'].search([('id','child_of',wh.lot_stock_id.id)])
            query = """
WITH onhand_query AS (
    SELECT
        sum(quantity) quantity,
        product_id
    FROM
        stock_quant sq
        LEFT JOIN stock_location sl ON sl.id = sq.location_id
    WHERE
        sl.usage = 'internal' AND
        sl.id in (%s)
    GROUP BY
        product_id
)
SELECT
    aas.sku sku,
    pt.name name,
    aas.stock aa_quantity,
    coalesce(oh.quantity, 0) odoo_quantity
FROM
    onhand_query oh
    LEFT JOIN product_product pp ON pp.id = oh.product_id
    LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id
    RIGHT JOIN aa_stock aas ON aas.sku = pt.default_code
WHERE
    coalesce(oh.quantity, 0) != aas.stock
""" % ','.join(map(str, locations.ids))
            self.env.cr.execute(query)
            aa_data += self.env.cr.fetchall()
        return aa_data
            
