###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

import logging

from odoo import _
from odoo.exceptions import AccessError, MissingError
from odoo.http import request, route

from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.addons.base_vat.models.res_partner import _ref_vat
from odoo.addons.payment.controllers.portal import PaymentProcessing
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.website.controllers.main import Website
from odoo.addons.website_sale.controllers.main import WebsiteSale

_logger = logging.getLogger(__name__)


class CustomerPortal(CustomerPortal):
    MANDATORY_BILLING_FIELDS = [
        "name",
        "phone",
        "email",
        "street",
        "city",
        "country_id",
        "zipcode",
    ]
    OPTIONAL_BILLING_FIELDS = ["state_id", "vat", "company_name", "street2"]

    def details_form_validate(self, data):
        error, error_message = super(CustomerPortal, self).details_form_validate(data)
        partner = request.env.user.partner_id
        if error.get("vat", False) == "error":
            country_val = data.get("country_id", False)
            if country_val:
                country = request.env["res.country"].sudo().browse(int(country_val))
            else:
                country = partner.country_id
            vat_country_code = country.code.lower()
            _ref_vat_no = "'CC##' (CC=Country Code, ##=VAT Number)"
            _ref_vat_no = _ref_vat.get(vat_country_code) or _ref_vat_no
            error_message.append(
                _(
                    "The VAT number either failed the VIES VAT validation check or did not respect the expected format "
                )
                + _ref_vat_no
            )
        return error, error_message

    @route(["/my/address/<int:child_pos>"], type="http", auth="user", website=True)
    def address(self, child_pos, redirect=None, **post):
        values = self._prepare_portal_layout_values()
        childs = request.env.user.partner_id.child_ids.sorted("type")
        partner = childs[child_pos]
        values.update(
            {
                "error": {},
                "error_message": [],
            }
        )

        if post and request.httprequest.method == "POST":
            error, error_message = self.details_form_validate(post)
            values.update({"error": error, "error_message": error_message})
            values.update(post)
            if not error:
                values = {key: post[key] for key in self.MANDATORY_BILLING_FIELDS}
                values.update(
                    {
                        key: post[key]
                        for key in self.OPTIONAL_BILLING_FIELDS
                        if key in post
                    }
                )
                for field in {"country_id", "state_id"} & set(values.keys()):
                    try:
                        values[field] = int(values[field])
                    except Exception:
                        values[field] = False
                values.update({"zip": values.pop("zipcode", "")})
                partner.sudo().write(values)
                if redirect:
                    return request.redirect(redirect)
                return request.redirect("/my/home")

        countries = request.env["res.country"].sudo().search([])
        states = request.env["res.country.state"].sudo().search([])

        values.update(
            {
                "form": "/my/address/%d" % child_pos,
                "partner": partner,
                "countries": countries,
                "states": states,
                "has_check_vat": hasattr(request.env["res.partner"], "check_vat"),
                "redirect": redirect,
                "page_name": "my_details",
            }
        )

        response = request.render("tameson_website.portal_address", values)
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @route(
        ["/my/orders/<int:order_id>/duplicate"],
        type="http",
        auth="public",
        methods=["POST"],
        website=True,
    )
    def duplicate(self, order_id, access_token=None, **post):
        try:
            order_sudo = self._document_check_access(
                "sale.order", order_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return request.redirect("/my")
        new_order = order_sudo.copy()
        new_order.write({"website_id": request.website.id})
        request.session["sale_order_id"] = new_order.id
        for line in new_order.order_line:
            if line.exists():
                new_order._cart_update(
                    product_id=line.product_id.id, line_id=line.id, add_qty=0
                )
        return request.redirect("/shop/cart")


class WebsiteSale(WebsiteSale):
    # Inherit to include manual payment to signature and confirm by portal customer
    @route(
        "/set/po_reference",
        type="json",
        auth="public",
        website=True,
        sitemap=False,
    )
    def set_po_reference(self, po_reference="", **post):
        order = request.website.sale_get_order()
        order.sudo().write({"client_order_ref": po_reference})
        return True

    @route(
        "/shop/payment/validate",
        type="http",
        auth="public",
        website=True,
        sitemap=False,
    )
    def payment_validate(self, transaction_id=None, sale_order_id=None, **post):
        if sale_order_id is None:
            order = request.website.sale_get_order()
        else:
            order = request.env["sale.order"].sudo().browse(sale_order_id)
            assert order.id == request.session.get("sale_last_order_id")

        if transaction_id:
            tx = request.env["payment.transaction"].sudo().browse(transaction_id)
            assert tx in order.transaction_ids()
        elif order:
            tx = order.get_portal_last_transaction()
        else:
            tx = None

        if not order or (order.amount_total and not tx):
            return request.redirect("/shop")

        if order and not order.amount_total and not tx:
            order.with_context(send_email=True).action_confirm()
            return request.redirect(order.get_portal_url())

        # clean context and session, then redirect to the confirmation page
        request.website.sale_reset()
        if tx and tx.state == "draft":
            return request.redirect("/shop")

        PaymentProcessing.remove_payment_transaction(tx)
        if tx.acquirer_id.provider == "transfer" and order:
            order.write(
                {
                    "require_payment": False,
                    "require_signature": True,
                }
            )
            return request.redirect(order.get_portal_url())
        return request.redirect("/shop/confirmation")

    def _get_shop_payment_values(self, order, **kwargs):
        values = super(WebsiteSale, self)._get_shop_payment_values(order, **kwargs)
        acquirers = values["acquirers"]
        if order.partner_id.property_payment_term_id.t_invoice_delivered_quantities:
            invoice_acq = int(
                request.env["ir.config_parameter"]
                .sudo()
                .get_param("Pay afterwards on invoice")
            )
            invoice_acq = request.env["payment.acquirer"].sudo().browse(invoice_acq)
            acquirers.insert(0, invoice_acq)
            values["acquirers"] = acquirers
        return values

    @route(
        "/add_sku",
        type="http",
        auth="public",
        website=True,
        sitemap=False,
    )
    def add_sku(self, sku="", **kw):
        error = ""
        order = request.website.sale_get_order(force_create=1)
        product = request.env["product.product"].search(
            [("default_code", "=ilike", sku)], limit=1
        )
        if product:
            order._cart_update(product_id=product.id, add_qty=1)
        else:
            error = "?add_sku_error=%s" % sku
        return request.redirect("/shop/cart%s" % error)


class WebsiteTameson(Website):
    @route(website=True, auth="public", sitemap=False)
    def web_login(self, redirect=None, *args, **kw):
        response = super(WebsiteTameson, self).web_login(redirect=redirect, *args, **kw)
        try:
            if not redirect and request.params["login_success"]:
                lang = request.env["res.users"].browse(request.uid).lang
                lang_code = request.env["res.lang"]._lang_get_code(lang)
                response.set_cookie("frontend_lang", lang_code)
        except Exception:
            _logger.warn("Error setting website language.")
        return response


class SignupHome(AuthSignupHome):
    def get_auth_signup_qcontext(self):
        qcontext = super(SignupHome, self).get_auth_signup_qcontext()
        set(qcontext.keys())
        if "reset_password" in request.httprequest.path:
            return qcontext
        login = qcontext["login"].lower()
        users = (
            request.env["res.users"]
            .sudo()
            .search([("login", "=ilike", login)], limit=1)
        )
        if not users:
            contact = (
                request.env["res.partner"]
                .sudo()
                .search([("email", "=ilike", login)], limit=1)
            )
            users = contact.user_ids or contact.parent_id.user_ids
        if users:
            qcontext["error"] = (
                """Account has other email as main account.
            This email is associated with the main
            account: %s, please login using that email address"""
                % users.login
            )
        return qcontext
