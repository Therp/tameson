# Copyright 2020 Therp BV <https://therp.nl>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import api, models


class StockRule(models.Model):
    _inherit = "stock.rule"

    @api.model
    def _prepare_purchase_order_line(
        self, product_id, product_qty, product_uom, company_id, values, po
    ):
        res = super(StockRule, self)._prepare_purchase_order_line(
            product_id, product_qty, product_uom, company_id, values, po
        )
        origin = values.get("group_id") and values.get("group_id").name.split("/")[0]
        if origin:
            origin_rec = self.env["sale.order"].search([("name", "=", origin)], limit=1)
            if origin_rec:
                res["ungrouped_origin"] = origin_rec.id
        return res
