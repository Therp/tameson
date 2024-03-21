###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

import json

from odoo import models
from odoo.tools.float_utils import float_compare, float_is_zero


def get_qty(data, delay):
    delays = []
    for item in data:
        if item["delay"] <= delay:
            stock = item["stock"] + item["max"]
        else:
            stock = item["stock"]
        qty = int(stock / item["bom_line_qty"])
        delays.append(qty)
    return min(delays or [0])


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    def set_bom_price(self, split=2000):
        for pos in range(0, len(self), split):
            self[pos : (pos + split)].with_delay().set_bom_sale_price_job()
        for pos in range(0, len(self), split):
            self[pos : (pos + split)].with_delay().set_bom_cost_price_job()

    def set_bom_sale_price_job(self):
        self.env.cr.execute(
            """select default_code, list_price from product_template
where default_code in (SELECT unnest(string_to_array(additional_cost, ',')) AS sku
FROM (select distinct additional_cost from product_template) as ac)"""
        )
        add_prices = dict(self.env.cr.fetchall())
        for bom in self:
            if not (
                float_is_zero(bom.product_qty, precision_digits=2)
                or float_is_zero(bom.product_tmpl_id.pack_factor, precision_digits=2)
            ):
                component_price = sum(
                    bom.bom_line_ids.mapped(
                        lambda l: l.product_id.list_price * l.product_qty
                    )
                )
                add_price = 0
                additional_costs = bom.product_tmpl_id.additional_cost or ""
                for sku in additional_costs.split(","):
                    add_price += add_prices.get(sku, 0)
                price = (
                    (component_price * bom.product_tmpl_id.pack_factor)
                    / bom.product_qty
                ) + add_price
                if (
                    float_compare(
                        bom.product_tmpl_id.list_price, price, precision_digits=2
                    )
                    != 0
                ):
                    bom.product_tmpl_id.write({"list_price": price})

    def set_bom_cost_price_job(self):
        self.env.cr.execute(
            """select default_code, id from product_template
where default_code in (SELECT unnest(string_to_array(additional_cost, ',')) AS sku
FROM (select distinct additional_cost from product_template) as ac)"""
        )
        add_prices = dict(self.env.cr.fetchall())
        for bom in self:
            product_tmpl_id = bom.product_tmpl_id
            product = product_tmpl_id.product_variant_id
            if not product_tmpl_id.active:
                continue
            add_price = 0
            additional_costs = bom.product_tmpl_id.additional_cost or ""
            for sku in additional_costs.split(","):
                adt = self.env["product.template"].browse(add_prices.get(sku, False))
                add_price += adt.standard_price
            price = product._compute_bom_price(bom) + add_price
            old = bom.product_tmpl_id.standard_price
            if float_compare(old, price, precision_digits=2) != 0:
                product.write({"standard_price": price})

    def set_bom_lead(self):
        for bom in self:
            if not bom.bom_line_ids:
                continue
            data = bom.bom_line_ids.mapped(
                lambda line: {
                    "stock": line.product_id.minimal_qty_available_stored,
                    "delay": line.product_id.seller_ids[:1].delay,
                    "bom_line_qty": line.product_qty,
                    "max": line.product_id.max_qty_order,
                }
            )
            delay = max(
                0
                if not float_is_zero(item["stock"], precision_digits=1)
                else item["delay"] + 1
                for item in data
            )
            delay_list = list(sorted({item["delay"] for item in data}))
            delay_list.insert(0, 0)
            delay_array = []
            max_qty_order = 0
            free_qty = 0
            for lead in delay_list:
                max_qty = get_qty(data, lead)
                if max_qty <= 0:
                    continue
                if lead == 0:
                    free_qty = max_qty
                else:
                    lead = lead + 1
                delay_array.append({"lead_time": lead, "max_qty": max_qty})
                if max_qty > max_qty_order:
                    max_qty_order = max_qty
            bom.product_tmpl_id.write(
                {
                    "minimal_qty_available_stored": free_qty,
                    "t_customer_lead_time": delay,
                    "max_qty_order": max_qty_order,
                    "max_qty_order_array": json.dumps(delay_array),
                }
            )
