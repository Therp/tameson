###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare
from odoo.tools.misc import get_lang

CURRENCIES = {"1": "EUR", "3": "GBP", "4": "USD"}

DOMAIN = {"1": "tameson.nl", "2": "tameson.co.uk", "3": "tameson.com"}


def _log_logging(env, message, function_name, path):
    env["ir.logging"].sudo().create(
        {
            "name": "Prestashop",
            "type": "server",
            "level": "WARN",
            "dbname": env.cr.dbname,
            "message": message,
            "func": function_name,
            "path": path,
            "line": "0",
        }
    )


import logging

_logger = logging.getLogger(__name__)


class SaleOrderPresta(models.Model):
    _inherit = "sale.order"

    prestashop_id = fields.Char(string="Prestashop ID", index=True, copy=False)
    prestashop_module = fields.Char(string="Prestashop Module", index=True, copy=False)
    prestashop_payment = fields.Char(
        string="Prestashop Payment", index=True, copy=False
    )
    prestashop_date_upd = fields.Datetime(
        string="Prestashop update time", index=True, copy=False
    )
    prestashop_config_id = fields.Many2one(
        string="Prestashop",
        comodel_name="prestashop.config",
        ondelete="set null",
        index=True,
        copy=False,
    )
    prestashop_state = fields.Char(
        string="Prestashop current state", index=True, copy=False
    )

    shipped_status_prestashop = fields.Boolean(
        string="Prestashop shipped", default=False, readonly=True, copy=False
    )
    force_all_qty_delivered = fields.Boolean(
        string="Force prestashop shipped", default=False, copy=False
    )

    _sql_constraints = [
        (
            "prestashop_id unique",
            "unique (prestashop_id)",
            _("Prestashop ID must be unique."),
        )
    ]

    def prestashop_cancel_confirm_cron(self):
        issues = []
        issues += self.prestashop_cancel_orders()
        issues += self.confirm_invoicepayment()
        partners = self.env.ref(
            "prestashop_sync.notification_prestashop_cron_issue"
        ).users.mapped("partner_id")
        if issues and partners:
            template = self.env.ref(
                "prestashop_sync.tameson_notify_prestashop_cron_issue"
            )
            template.with_context(issues=issues).send_mail(
                self.env.user.partner_id.id,
                force_send=True,
                email_values={"recipient_ids": [(6, 0, partners.ids)]},
            )

    def prestashop_cancel_orders(self):
        issues = []
        CancelOrders = self.env["sale.order"].search(
            [
                ("state", "!=", "cancel"),
                ("prestashop_id", "!=", False),
                ("prestashop_state", "in", ("6", "146")),
            ]
        )
        for order in CancelOrders:
            try:
                if order.payment_term_id.name == "Prepayment":
                    for invoice in order.invoice_ids:
                        if invoice.invoice_payment_state == "not_paid":
                            invoice.button_draft()
                            invoice.button_cancel()
                order.action_cancel()
            except Exception as e:
                _logger.warning(str(e))
                issues.append((order.name, order.id, str(e)))
                continue
        return issues

    def create_from_prestashop(self, task_uuid, order, **kwargs):
        order_data = order["order"]
        prestashop_id = order_data["id"]
        if order["invoice"]["country_code"].lower() == "gb":
            partner, delivery, invoice = (
                self.env["res.partner"]
                .with_context(no_vat_validation=True)
                .match_or_create_prestashop(order)
            )
        else:
            partner, delivery, invoice = self.env[
                "res.partner"
            ].match_or_create_prestashop(order)
        prestashop_module = order_data["module"]
        prestashop_payment = order_data["payment"]
        prestashop_date_upd = order_data["date_upd"]
        prestashop_config_id = order["config_id"]
        config_id = self.env["prestashop.config"].browse(prestashop_config_id)
        currency_id = self.env["res.currency"].search(
            [("name", "=", CURRENCIES[order_data["id_currency"]])], limit=1
        )
        pricelist_id = self.env["product.pricelist"].search(
            [("currency_id", "=", currency_id.id)], limit=1
        )
        if not pricelist_id:
            raise UserError(
                "%s currency pricelist not found."
                % CURRENCIES[order_data["id_currency"]]
            )
        partner.property_product_pricelist = pricelist_id
        lines = []
        lang = get_lang(self.env, partner.lang).code
        for line in order_data["order_rows"]:
            product_id = self.env["product.product"].search(
                [("default_code", "=ilike", line["product_reference"])], limit=1
            )
            if not product_id:
                raise UserError(
                    "Product for reference %s not found." % line["product_reference"]
                )
                # product_id = self.env['product.product'].create({'default_code': line['product_reference'], 'name': line['product_name'], 'type': 'product'})
            lines.append(
                (
                    0,
                    0,
                    {
                        "product_id": product_id.id,
                        "name": product_id.with_context(
                            lang=lang
                        ).get_product_multiline_description_sale(),
                        "product_uom_qty": float(line["product_quantity"]),
                        "price_unit": float(line["unit_price_tax_excl"]),
                    },
                )
            )
        order_vals = {
            "partner_id": partner.id,
            "payment_term_id": partner.property_payment_term_id.id,
            "partner_shipping_id": delivery.id,
            "partner_invoice_id": invoice.id,
            "pricelist_id": pricelist_id.id,
            "prestashop_id": prestashop_id,
            "prestashop_module": prestashop_module,
            "prestashop_payment": prestashop_payment,
            "t_invoice_policy": "delivery"
            if prestashop_module == "invoicepayment"
            else False,
            "prestashop_date_upd": prestashop_date_upd,
            "prestashop_config_id": prestashop_config_id,
            "order_line": lines,
            "presta_ups_access_point_country": order_data.get(
                "ups_country_iso", {}
            ).get("value", False),
            "presta_ups_access_point_id": order_data.get("ups_id_access_point", {}).get(
                "value", False
            ),
            "prestashop_state": order_data["current_state"],
            "client_order_ref": order_data.get("user_reference", {}).get(
                "value", False
            ),
            "origin": "%s - %s - %s"
            % (
                DOMAIN.get(order_data.get("id_shop", ""), ""),
                prestashop_id,
                order_data.get("reference", ""),
            ),
            "source_id": config_id.source_id.id,
        }
        carrier = order_data.get("id_carrier", "0")
        carrier_id = bool(carrier) and self.env["delivery.carrier"].search(
            [("prestashop_carrier_ids", "=", carrier)], limit=1
        )
        if carrier_id:
            lines.append(
                (
                    0,
                    0,
                    {
                        "product_id": carrier_id.product_id.id,
                        "product_uom_qty": 1,
                        "name": carrier_id.product_id.name,
                        "price_unit": order_data.get("total_shipping_tax_excl", 0),
                        "is_delivery": True,
                    },
                )
            )
            order_vals.update({"carrier_id": carrier_id.id, "order_line": lines})
        else:
            if carrier:
                raise UserError(
                    "Carrier name doesn't match with any shipping method in Odoo"
                )

        total_discounts_tax_excl = float(order_data.get("total_discounts_tax_excl", 0))
        if total_discounts_tax_excl > 0:
            lines.append(
                (
                    0,
                    0,
                    {
                        "product_id": config_id.discount_product_id.id,
                        "product_uom_qty": 1,
                        "name": "Webshop discount",
                        "price_unit": -total_discounts_tax_excl,
                    },
                )
            )

        Order = self.create(order_vals)
        Order.onchange_partner_shipping_id()
        Order.recompute()
        Order._compute_tax_id()
        for line in Order.order_line:
            line._onchange_product_id_set_customer_lead()
        invoice_email = order_data.get("user_invoice_email", {}).get("value", False)
        if invoice_email:
            Order.partner_invoice_id.email = invoice_email
        Order.flush()
        return Order.name

    def update_from_prestashop(self, task_uuid, so_id, order, **kwargs):
        prestashop_module = order["module"]
        prestashop_payment = order["payment"]
        prestashop_date_upd = order["date_upd"]
        so_id = self.browse(so_id)
        so_id.write(
            {
                "prestashop_module": prestashop_module,
                "prestashop_payment": prestashop_payment,
                "prestashop_date_upd": prestashop_date_upd,
                "prestashop_state": order["current_state"],
            }
        )
        return True

    def prestashop_order_process(self, task_uuid, so_id, data, **kwargs):
        self = self.browse(so_id)
        if self.fiscal_position_id.name.startswith("OSS"):
            self.prestashop_match_price()
        presta_total = float(data["total_paid_tax_incl"])
        price_difference = abs(presta_total - self.amount_total)
        ## float_compare 1 means price difference greater allowed value
        if (
            float_compare(
                price_difference,
                self.prestashop_config_id.price_def_allowed,
                precision_digits=2,
            )
            == 1
        ):
            raise UserError(
                "Total amount mismatch odoo: %.2f presta: %.2f"
                % (self.amount_total, presta_total)
            )
        module = data["module"]
        if module == "ps_wirepayment":
            if self.invoice_ids:
                return True
            prepayment = self.env["account.payment.term"].search(
                [("name", "=", "Prepayment")], limit=1
            )
            self.write(
                {
                    "payment_term_id": prepayment.id,
                    "t_invoice_policy": "order",
                    "prestashop_module": module,
                }
            )
            wizard = (
                self.env["sale.advance.payment.inv"]
                .with_context(
                    {
                        "active_model": self._name,
                        "active_id": self.id,
                        "active_ids": self.ids,
                    }
                )
                .create({"advance_payment_method": "delivered"})
            )
            wizard.create_invoices()
            self.invoice_ids.action_post()
        else:
            if self.state == "sale":
                return True
            self.write({"prestashop_module": module, "channel_process_payment": True})
            self.action_confirm()
        return True

    def confirm_invoicepayment(self):
        issues = []
        for sale in self.search(
            [
                ("state", "in", ("draft", "sent")),
                ("prestashop_module", "=", "invoicepayment"),
            ]
        ):
            try:
                sale.action_confirm()
            except Exception as e:
                _logger.warning(str(e))
                issues.append((sale.name, sale.id, str(e)))
                continue
        return issues

    def process_channel_payment(self):
        for record in self.search(
            [
                ("channel_process_payment", "=", True),
                ("prestashop_id", "!=", False),
                ("state", "=", "sale"),
            ]
        ):
            if (
                record.prestashop_module
                and record.prestashop_module == "mollie"
                and record.prestashop_payment == "PayPal"
            ) or (
                record.prestashop_module
                and record.prestashop_module == "adyencw_paypal"
            ):
                if record.currency_id.name == "USD":
                    name = "PayPal USD"
                elif record.currency_id.name == "GBP":
                    name = "PayPal GBP"
                else:
                    name = "PayPal EUR"
            elif record.prestashop_module and record.prestashop_module == "mollie":
                name = "Mollie"
            elif record.prestashop_module and record.prestashop_module.startswith(
                "adyencw"
            ):
                name = "adyen"
            else:
                msg = "Module name not match %s" % record.name
                _log_logging(self.env, msg, "process_payment", record.id)
                _logger.warn(msg)
                continue

            journal_id = self.env["account.journal"].search(
                [("type", "in", ("bank", "cash")), ("name", "ilike", name)], limit=1
            )

            if not journal_id:
                msg = "Journal not found %s" % record.name
                _log_logging(self.env, msg, "process_payment", record.id)
                _logger.warn(msg)
                continue

            try:
                for invoice in record.invoice_ids.filtered(
                    lambda i: i.state != "cancel" and i.invoice_payment_state != "paid"
                ):
                    invoice.action_register_payment_direct(journal_id=journal_id.id)
                record.write({"channel_process_payment": False})
            except Exception as e:
                msg = "Prestashop payment creation error: %s %s" % (str(e), record.name)
                _log_logging(self.env, msg, "process_channel_payment", record.id)
                _logger.warn(msg)
                continue
        return super(SaleOrderPresta, self).process_channel_payment()

    def _get_sale_order_has_issues(self):
        vals = super(SaleOrderPresta, self)._get_sale_order_has_issues()
        orders = self.search(
            [
                ("prestashop_id", "!=", False),
                ("state", "=", "sale"),
                ("prestashop_module", "!=", "invoicepayment"),
                ("payment_term_id.t_invoice_delivered_quantities", "=", False),
            ]
        ).filtered(
            lambda o: not o.invoice_ids.filtered(
                lambda i: i.invoice_payment_state == "paid"
            )
        )
        if orders:
            vals.append(
                {
                    "name": "Prestashop order confirmed but invoice not paid",
                    "orders": orders.mapped(lambda o: (o.id, o.name)),
                }
            )
        not_confirmed_orders = self.search(
            [
                ("channel_process_payment", "=", True),
                ("state", "not in", ("sale", "cancel")),
            ]
        )
        if not_confirmed_orders:
            vals.append(
                {
                    "name": "Prestashop orders not confirmed.",
                    "orders": not_confirmed_orders.mapped(lambda o: (o.id, o.name)),
                }
            )
        return vals

    def prestashop_match_price(self):
        prestashop_rate = 1.21
        for line in self.order_line:
            tax_rate = (
                100
                + sum(
                    line.tax_id.filtered(lambda t: not t.price_include).mapped("amount")
                )
            ) / 100
            line.price_unit = line.price_unit * prestashop_rate / tax_rate
