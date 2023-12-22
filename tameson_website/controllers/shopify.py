###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

import json
import logging
from urllib.parse import urlparse

import werkzeug
from multipass import Multipass
from werkzeug.exceptions import NotFound

from odoo.http import Controller, request, route

_logger = logging.getLogger(__name__)


class Shopify(Controller):
    @route(["/shopify_hosts"], type="http", auth="user", website=True)
    def shopify_hosts(self, **kw):
        instances = (
            request.env["shopify.instance.ept"]
            .sudo()
            .search([("shopify_multipass_secret", "!=", False)])
        )
        return request.render(
            "tameson_website.portal_shopify_hosts", {"instances": instances}
        )

    @route(
        ["/shopify/cart_migrate"],
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
        csrf=False,
    )
    def shopify_cart_migration(self, data, **kw):
        data = json.loads(data)
        order = request.website.sale_get_order(update_pricelist=True, force_create=True)
        order.sudo().order_line.unlink()
        for item in data.get("items", []):
            sku = item["sku"]
            qty = item["quantity"]
            pp = (
                request.env["product.product"]
                .sudo()
                .search([("default_code", "=ilike", sku)], limit=1)
                .id
            )
            if pp:
                order.sudo()._cart_update(product_id=pp, set_qty=qty)
        return request.redirect("/shop/cart")

    @route(
        ["/shopify_auth", "/shopify_auth/<int:instance_id>"],
        type="http",
        auth="user",
        website=True,
    )
    def shopify_auth(self, instance_id=None, **kw):
        instance = request.env["shopify.instance.ept"].sudo()
        shopify_page = request.session.get("shopify_page", False)
        if shopify_page:
            request.session["shopify_page"] = False
            url_obj = urlparse(shopify_page)
            hostname = url_obj.hostname
            if hostname:
                instance = instance.search(
                    [
                        ("shopify_multipass_host", "ilike", hostname),
                        ("shopify_multipass_secret", "!=", False),
                    ],
                    limit=1,
                )
                if "checkouts" in shopify_page:
                    shopify_page = "/cart"
            else:
                shopify_page = False
        if not instance:
            instance = instance.browse(instance_id)
        if not instance:
            instance = request.env.user.partner_id.country_id.shopify_instance_id
        if not instance:
            params = request.env["ir.config_parameter"].sudo()
            instance_id = params.get_param("default.shopify.instance", False)
            if instance_id:
                instance = instance.browse(int(instance_id))
        if not instance:
            instance = instance.search(
                [("shopify_multipass_secret", "!=", False)], limit=1
            )
        if not instance:
            raise NotFound("No Shopify Instance Added.")
        partner = request.env.user.partner_id
        partner_data = partner._get_shopify_partner_data()
        partner_data["return_to"] = shopify_page or "/"
        multipass = Multipass(instance.shopify_multipass_secret)
        url = multipass.generateURL(partner_data, instance.shopify_multipass_host)
        return werkzeug.utils.redirect(url)

    @route(
        ["/shopify/email_check"],
        type="json",
        auth="public",
        csrf=False,
        methods=["POST", "OPTIONS"],
        cors="*",
    )
    def check_email(self, email, **kw):
        partner = (
            request.env["res.partner"]
            .sudo()
            .search([("email", "=", email)], order="parent_id DESC", limit=1)
        )
        checkout = bool(partner) and (
            partner.property_payment_term_id.t_invoice_delivered_quantities
            or partner.property_product_pricelist.discount_policy == "without_discount"
        )
        value = {
            "email": email,
            "ODOO-checkout": checkout,
        }
        return value
