###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from datetime import datetime

from dateutil.relativedelta import relativedelta

from odoo import SUPERUSER_ID, fields, models
from odoo.tools import float_compare


def filter_orders(order):
    difference = abs(order.shopify_total_price - order.amount_total)
    return float_compare(difference, 0.05, precision_digits=2) != 1


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    virtual_available_at_date = fields.Float(compute_sudo=True)
    scheduled_date = fields.Datetime(compute_sudo=True)
    free_qty_today = fields.Float(compute_sudo=True)
    qty_available_today = fields.Float(compute_sudo=True)
    warehouse_id = fields.Many2one(compute_sudo=True)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    shopify_total_price = fields.Float(readonly=True)

    def prepare_shopify_order_vals(
        self,
        instance,
        partner,
        shipping_address,
        invoice_address,
        order_response,
        payment_gateway,
        workflow,
    ):
        vals = super(SaleOrder, self).prepare_shopify_order_vals(
            instance,
            partner,
            shipping_address,
            invoice_address,
            order_response,
            payment_gateway,
            workflow,
        )
        po_ref = order_response.get("metafields", {}).get("po_reference", False)
        name = order_response.get("name")
        if po_ref:
            vals.update({"client_order_ref": "%s - %s" % (po_ref, name)})
        vals.update({"origin": "%s - %s" % (instance.name, name)})
        return vals

    def prepare_shopify_order_vals(
        self,
        instance,
        partner,
        shipping_address,
        invoice_address,
        order_response,
        payment_gateway,
        workflow,
    ):
        vals = super(SaleOrder, self).prepare_shopify_order_vals(
            instance,
            partner,
            shipping_address,
            invoice_address,
            order_response,
            payment_gateway,
            workflow,
        )
        total_price = float(order_response.get("total_price", 0))
        vals.update({"shopify_total_price": total_price})
        return vals

    def import_shopify_orders(self, order_data_queue_line, log_book_id):
        order_id = super(SaleOrder, self).import_shopify_orders(
            order_data_queue_line, log_book_id
        )
        if order_id:
            difference = abs(order_id.shopify_total_price - order_id.amount_total)
            if float_compare(difference, 0.05, precision_digits=2) == 1:
                msg = "Total amount missmatch shopify: %.2f odoo: %.2f" % (
                    order_id.shopify_total_price,
                    order_id.amount_total,
                )
                order_id.activity_schedule(
                    "mail.mail_activity_data_warning",
                    datetime.today().date(),
                    note=msg,
                    user_id=order_id.user_id.id or SUPERUSER_ID,
                )
        return order_id

    def shopify_create_sale_order_line(
        self,
        line,
        product,
        quantity,
        product_name,
        order_id,
        price,
        order_response,
        is_shipping=False,
        previous_line=False,
        is_discount=False,
    ):
        line_id = super(SaleOrder, self).shopify_create_sale_order_line(
            line,
            product,
            quantity,
            product_name,
            order_id,
            price,
            order_response,
            is_shipping,
            previous_line,
            is_discount,
        )
        tax_included = order_response.get("taxes_included")
        if tax_included:
            tax = sum(float(l["rate"]) for l in line["tax_lines"])
            line_id.price_unit = line_id.price_unit / (1 + tax)
            line_id.with_context(round=False)._compute_amount()
        return line_id

    def process_orders_and_invoices_ept(self):
        order = self.filtered(lambda o: filter_orders(o))
        return super(SaleOrder, order).process_orders_and_invoices_ept()

    def _get_sale_order_has_issues(self):
        vals = super(SaleOrder, self)._get_sale_order_has_issues()
        from_date = datetime.now() - relativedelta(hours=1)
        draft_queue = self.env["shopify.order.data.queue.ept"].search(
            [("state", "!=", "completed"), ("create_date", "<=", from_date)]
        )
        draft_orders = self.env["sale.order"].search(
            [
                ("state", "in", ("draft", "sent")),
                ("shopify_order_id", "!=", False),
                ("create_date", "<=", from_date),
            ]
        )
        if draft_queue:
            vals.append(
                {
                    "name": "Shopify Order Queue Pending",
                    "orders": [
                        (len(draft_queue), "Shopify order data queue pending import")
                    ],
                }
            )
        if draft_orders:
            vals.append(
                {
                    "name": "Shopify Orders Draft",
                    "orders": draft_orders.mapped(lambda o: (o.id, o.name)),
                }
            )
        return vals


class AccountMove(models.Model):
    _inherit = "account.move"

    def prepare_payment_dict(self, work_flow_process_record):
        vals = super().prepare_payment_dict(work_flow_process_record)
        if work_flow_process_record.currency_journal:
            mapping = work_flow_process_record.mapping_ids.filtered(
                lambda m: m.currency_id.id == self.currency_id.id
            )
            if mapping:
                vals["journal_id"] = mapping.journal_id.id
        return vals
