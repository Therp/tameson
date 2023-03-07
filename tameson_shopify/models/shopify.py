###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

import json
import logging

from odoo import api, fields, models

from odoo.addons.shopify_ept import shopify
from odoo.addons.shopify_ept.shopify.pyactiveresource.util import xml_to_dict

_logger = logging.getLogger(__name__)


def process_metafields(metavals):
    data = {}
    for mf in metavals:
        mfd = mf.to_dict()
        data[mfd["key"]] = mfd["value"]
    return data


class ShopifyOrderDataQueueLineEpt(models.Model):
    _inherit = "shopify.order.data.queue.line.ept"

    def create_order_data_queue_line(
        self, order_ids, instance, created_by="import", process_immediately=False
    ):
        count = 0
        one_time_create = True
        order_ids.reverse()
        order_queue_list = []
        instance.connect_in_shopify()
        for order_id in order_ids:

            if created_by == "webhook" and not process_immediately:
                order_queue_id, one_time_create = self.search_webhook_order_queue(
                    created_by, instance, order_id, one_time_create
                )
                if len(order_queue_id.order_data_queue_line_ids) > 50:
                    one_time_create = True
                order_queue_list.append(order_queue_id.id)

            if one_time_create:
                order_queue_id = self.shopify_create_order_queue(instance, created_by)
                order_queue_list.append(order_queue_id.id)
                _logger.info(
                    "Shopify Order Queue created. Queue name is  {}".format(
                        order_queue_id.name
                    )
                )
                one_time_create = False

            """We got the order response from webhook then that response formate is JSON,
               so we did not require to convert it."""
            if not created_by == "webhook":
                metavals = process_metafields(order_id.metafields())
                result = xml_to_dict(order_id.to_xml())
                result["order"].update({"metafields": metavals})
                invoice_email = metavals.get("invoice_email", False)
                if invoice_email:
                    result["order"]["billing_address"].update(
                        {"invoice_email": invoice_email}
                    )
                shopify_sale_order_id = self.env["sale.order"].search(
                    [
                        (
                            "shopify_order_id",
                            "=",
                            result.get("order").get("id")
                            if result.get("order")
                            else False,
                        ),
                        ("shopify_instance_id", "=", instance and instance.id or False),
                    ]
                )
                if shopify_sale_order_id:
                    continue
            else:
                # We we got response from webhook
                order = shopify.Order.find(order_id.get("id"))
                metavals = process_metafields(order.metafields())
                invoice_email = metavals.get("invoice_email", False)
                if invoice_email:
                    order_id["billing_address"].update({"invoice_email": invoice_email})
                order_id.update({"metafields": metavals})
                result = {"order": order_id}

            try:
                customer_name = "%s %s" % (
                    result.get("order").get("customer").get("first_name"),
                    result.get("order").get("customer").get("last_name"),
                )
                customer_email = result.get("order").get("customer").get("email")
                if customer_name == "None None":
                    customer_name = (
                        result.get("order")
                        .get("customer")
                        .get("default_address")
                        .get("name")
                    )
            except:
                customer_name = False
                customer_email = False

            data = json.dumps(result)
            order_queue_line_vals = {
                "shopify_order_id": result.get("order").get("id")
                if result.get("order")
                else False,
                "shopify_instance_id": instance and instance.id or False,
                "order_data": data,
                "name": result.get("order").get("name") or "",
                "customer_name": customer_name,
                "customer_email": customer_email,
                "shopify_order_data_queue_id": order_queue_id
                and order_queue_id.id
                or False,
                "state": "draft",
            }
            self.create(order_queue_line_vals)
            count += 1
            if count == 50:
                count = 0
                one_time_create = True
        return order_queue_list


class ShopifyInstanceEpt(models.Model):
    _inherit = "shopify.instance.ept"

    shopify_multipass_host = fields.Char(
        "Shop Address",
    )
    shopify_multipass_secret = fields.Char(
        "Multipass secret",
    )
    export_done_webhook = fields.Char()
    customer_webhook = fields.Char()
    multipass_country_ids = fields.One2many(
        comodel_name="res.country",
        inverse_name="shopify_instance_id",
    )

    def create_bulk_export_wh(self):
        odoo_host = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        query = """mutation {
  webhookSubscriptionCreate(
    topic: BULK_OPERATIONS_FINISH
    webhookSubscription: {
      format: JSON,
      callbackUrl: "%s/shopify/export_done/%d"}
  ) {
    userErrors {
      field
      message
    }
    webhookSubscription {
      legacyResourceId
    }
  }
}""" % (
            odoo_host,
            self.id,
        )
        session = shopify.Session(self.shopify_host, "2021-04", self.shopify_password)
        shopify.ShopifyResource.activate_session(session)
        result = json.loads(shopify.GraphQL().execute(query))
        self.export_done_webhook = result["data"]["webhookSubscriptionCreate"][
            "webhookSubscription"
        ]["legacyResourceId"]

    def delete_bulk_export_wh(self):
        self.delete_wh(self.export_done_webhook)
        self.export_done_webhook = False

    def delete_wh(self, webhook_id):
        self.connect_in_shopify()
        webhook = shopify.Webhook().find(webhook_id)
        webhook.destroy()

    def create_customer_webhook(self):
        self.connect_in_shopify()
        odoo_host = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        create = shopify.Webhook.create(
            {
                "topic": "customers/create",
                "address": "%s/shopify/customer_create/%d" % (odoo_host, self.id),
                "format": "json",
            }
        )
        update = shopify.Webhook.create(
            {
                "topic": "customers/update",
                "address": "%s/shopify/customer_update/%d" % (odoo_host, self.id),
                "format": "json",
            }
        )
        self.customer_webhook = "%d,%d" % (create.id, update.id)

    def delete_customer_webhook(self):
        for id in self.customer_webhook.split(","):
            self.delete_wh(id)
        self.customer_webhook = False

    def process_customer_webhook_data(self, data):
        id = data["id"]
        email = data["email"]
        self.connect_in_shopify()
        shopify_customer = shopify.Customer.find(id)
        Partner = self.env["res.partner"]
        shopify_te = data["tax_exempt"]
        contact = Partner.search(
            [("email", "=ilike", email)], order="parent_id DESC", limit=1
        )
        if not contact:
            return {"result": "Email doesn't match with any contact %s" % email}
        odoo_te = bool(contact and contact.get_tax_exempt())
        if odoo_te != shopify_te:
            shopify_customer.tax_exempt = odoo_te
            shopify_customer.save()
        metafields = shopify_customer.metafields()
        vat_match = False
        invoice_email_match = False
        odoo_invoice_email = contact.get_invoice_email()
        for field in metafields:
            if field.key == "vat_number":
                if field.value != contact.vat:
                    field.destroy()
                else:
                    vat_match = True
            if field.key == "invoice_email":
                if field.value != odoo_invoice_email:
                    field.destroy()
                else:
                    invoice_email_match = True
        if not vat_match:
            shopify_customer.add_metafield(
                shopify.Metafield(
                    {
                        "key": "vat_number",
                        "value": contact.vat,
                        "type": "single_line_text_field",
                        "namespace": "sufio",
                    }
                )
            )
        if not invoice_email_match:
            shopify_customer.add_metafield(
                shopify.Metafield(
                    {
                        "key": "invoice_email",
                        "value": odoo_invoice_email,
                        "type": "single_line_text_field",
                        "namespace": "details",
                    }
                )
            )
        return {
            "vat_match": vat_match,
            "invoice_email_match": invoice_email_match,
            "tax_exempt_match": odoo_te == shopify_te,
        }


class ResCountry(models.Model):
    _inherit = "res.country"

    shopify_instance_id = fields.Many2one(
        comodel_name="shopify.instance.ept",
        ondelete="restrict",
    )


class ShopifyProcessImportExport(models.TransientModel):
    _inherit = "shopify.process.import.export"

    shopify_operation_t = fields.Selection(
        [
            # ('sync_product',
            #  'Sync New Products - Set To Queue'),
            # ('sync_product_by_remote_ids',
            #  'Sync New Products - By Remote Ids'),
            ("import_orders", "Import Orders"),
            ("import_orders_by_remote_ids", "Import Orders - By Remote Ids"),
            ("update_order_status", "Update Order Status"),
            # ('import_customers',
            #  'Import Customers'),
            ("export_stock", "Export Stock"),
            # ('import_stock',
            #  'Import Stock'),
            # ('update_order_status',
            #  'Update Order Status'),
            # ('import_payout_report',
            #  'Import Payout Report'),
        ],
        string="Operation",
        default="import_orders_by_remote_ids",
    )

    @api.onchange("shopify_operation_t")
    def onchange_shopify_operation_t(self):
        self.shopify_operation = self.shopify_operation_t


def nested_set_presentment(data_dict):
    for k, v in data_dict.items():
        if k.endswith("_set") and isinstance(v, dict):
            kk = k.replace("_set", "")
            if kk in data_dict:
                data_dict[kk] = v["presentment_money"]["amount"]
        elif isinstance(v, dict):
            nested_set_presentment(v)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    nested_set_presentment(item)


class ShopifyOrderDataQueueLineEpt(models.Model):
    _inherit = "shopify.order.data.queue.line.ept"

    def create(self, vals):
        data = json.loads(vals["order_data"])
        presentment_cur = data["order"]["presentment_currency"]
        if presentment_cur != "EUR":
            data["order"]["currency"] = presentment_cur
            nested_set_presentment(data)
        vals["order_data"] = json.dumps(data)
        return super(ShopifyOrderDataQueueLineEpt, self).create(vals)


class SaleWorkflowProcess(models.Model):
    _inherit = "sale.workflow.process.ept"

    currency_journal = fields.Boolean()

    mapping_ids = fields.One2many(
        comodel_name="currency.journal.mapping",
        inverse_name="workflow_id",
    )


class CurrencyJournal(models.Model):
    _name = "currency.journal.mapping"
    _description = "CurrencyJournal"

    _rec_name = "currency_id"
    _order = "currency_id ASC"

    workflow_id = fields.Many2one(
        comodel_name="sale.workflow.process.ept",
        ondelete="restrict",
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        ondelete="restrict",
    )
    journal_id = fields.Many2one(
        comodel_name="account.journal",
        ondelete="restrict",
    )
