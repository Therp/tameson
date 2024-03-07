from datetime import datetime, timedelta

from odoo import api, fields, models
from odoo.tools.float_utils import float_compare
from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT as DSDF

from odoo.addons.queue_job.delay import chain, group


def list_split(listA, n):
    for start in range(0, len(listA), n):
        stop = len(listA) if len(listA) < n + start else n + start
        every_chunk = listA[start:stop]
        yield every_chunk


class ProductProduct(models.Model):
    _inherit = "product.product"

    def action_view_stock_moves(self):
        self.ensure_one()
        action = self.env.ref("stock.stock_move_action").read()[0]
        action.update(
            {
                "domain": [("product_id", "=", self.id)],
                "context": {"create": 0, "search_default_future": True},
            }
        )
        return action


class ProductTemplate(models.Model):
    _inherit = "product.template"

    minimal_qty_available_stored = fields.Float(
        digits="Product Unit of Measure",
        string="Minimal QTY Available (Forcasted Qty)",
        help="Odoo Free Quantity field on Product variant, \
        stored on Product template for faster export",
    )

    @api.model
    def set_buy_route(self):
        buy_id = self.env.ref("purchase_stock.route_warehouse0_buy")
        self.write({"route_ids": [(6, 0, [buy_id.id])]})

    @api.model
    def set_mtos_buy_route(self):
        buy_id = self.env.ref("purchase_stock.route_warehouse0_buy")
        mtos_id = self.env.ref("stock_mts_mto_rule.route_mto_mts")
        self.write({"route_ids": [(6, 0, [buy_id.id, mtos_id.id])]})

    def cron_store_product_data(self, duration=60, split=500):
        lasthour = datetime.now() - timedelta(minutes=duration)
        lasthour_formatted = lasthour.strftime(DSDF)
        domain = [
            "|",
            ("create_date", ">", lasthour_formatted),
            ("write_date", ">", lasthour_formatted),
        ]
        move_products = (
            self.env["stock.move"].search(domain).mapped("product_id.product_tmpl_id")
        )
        new_created = self.env["product.template"].search(
            [("create_date", ">", lasthour_formatted)]
        )
        supplier_info_updated = (
            self.env["product.supplierinfo"].search(domain).mapped("product_tmpl_id")
        )
        templates = move_products + new_created + supplier_info_updated
        if not templates:
            return
        templates.store_product_data(split)

    def store_product_data(self, split):
        variants = self.mapped("product_variant_id")
        bom_ids = (
            self.env["mrp.bom.line"]
            .search([("product_id", "in", variants.ids)])
            .mapped("bom_id")
        )
        # Store free qty on minimal_qty_available_stored
        min_grouped = []
        for pos in range(0, len(self), split):
            job = self[pos : (pos + split)].delayable().update_min_qty()
            min_grouped.append(job)
        # set bom product leads
        bom_grouped = []
        for pos in range(0, len(bom_ids), split):
            job = bom_ids[pos : (pos + split)].delayable().set_bom_lead()
            bom_grouped.append(job)
        # non-bom-lead
        non_bom_grouped = []
        for pos in range(0, len(self), split):
            job = self[pos : (pos + split)].delayable().set_non_bom_lead()
            non_bom_grouped.append(job)
        chain(group(*min_grouped), group(*non_bom_grouped), group(*bom_grouped)).delay()

    def update_min_qty(self):
        min_qty_warehouse = int(
            self.env["ir.config_parameter"].sudo().get_param("min_qty_warehouse", 0)
        )
        if min_qty_warehouse:
            self = self.with_context(warehouse=min_qty_warehouse)
        for pt in self:
            min_qty = pt.minimal_qty_available_stored
            free_qty = pt.product_variant_id.free_qty
            if float_compare(min_qty, free_qty, precision_digits=2) != 0:
                pt.write({"minimal_qty_available_stored": free_qty})

    def cron_store_all_product_data(self, split=5000):
        pts = self.search([("bom_ids", "=", False)])
        pts.store_product_data(split)

    def action_view_stock_moves(self):
        self.ensure_one()
        action = self.env.ref("stock.stock_move_action").read()[0]
        action.update(
            {
                "domain": [("product_id", "in", self.product_variant_ids.ids)],
                "context": {"create": 0, "search_default_future": True},
            }
        )
        return action
