###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    def match_or_create_prestashop(self, order):
        customer_data = order["customer"]
        invoice_data = order["invoice"]
        delivery_data = order["delivery"]
        email = customer_data.get("email", False)
        partner = self.browse()
        if email:
            partner = self.search(
                [("email", "=ilike", email), ("parent_id", "=", False)], limit=1
            )
            partner.write(
                {
                    "name": "%s %s"
                    % (
                        customer_data.get("firstname", ""),
                        customer_data.get("lastname", ""),
                    ),
                }
            )
        if not partner:
            country_id = (
                self.env["res.country"]
                .search(
                    [("code", "=ilike", invoice_data.get("country_code", ""))], limit=1
                )
                .id
            )
            partner = self.create(
                {
                    "name": "%s %s"
                    % (
                        customer_data.get("firstname", ""),
                        customer_data.get("lastname", ""),
                    ),
                    "email": email,
                    "country_id": country_id,
                }
            )
        childs = self.search(
            [
                ("id", "child_of", partner.id),
                ("type", "in", ("invoice", "delivery", "other")),
            ]
        )
        if invoice_data:
            invoice, childs = childs.address_to_partner_prestashop(
                invoice_data, "invoice", partner
            )
            vat_number = invoice_data.get("vat_number", False)
            company = invoice_data.get("company", False)
            partner_data = {
                "phone": invoice.phone,
                "street": invoice.street,
                "street2": invoice.street2,
                "zip": invoice.zip,
            }
            if vat_number:
                try:
                    partner.write(
                        {"vat": vat_number, "country_id": invoice.country_id.id}
                    )
                except Exception:
                    _logger.warn("VAT number validation failed.")
                    partner_data.update({"country_id": invoice.country_id.id})
            if company:
                partner_data.update({"name": company, "is_company": True})
            if partner_data:
                partner.write(partner_data)
            partner.onchange_country_lang()
            partner.extract_house_from_street()
        else:
            invoice = partner
        if not delivery_data:
            delivery = invoice
        else:
            delivery, childs = childs.address_to_partner_prestashop(
                delivery_data, "delivery", partner
            )
        if childs:
            childs.write({"type": "other"})
        if partner.vat and partner.country_id.country_group_ids.filtered(
            lambda g: g.name == "Europe ex NL"
        ):
            partner.property_account_position_id = self.env[
                "account.fiscal.position"
            ].search([("name", "=", "EU landen")])
        elif not partner.country_id.country_group_ids.filtered(
            lambda g: g.name == "Europe"
        ):
            partner.property_account_position_id = self.env[
                "account.fiscal.position"
            ].search([("name", "=", "Niet-EU landen")])
        else:
            pass
        return partner, delivery, invoice

    def address_to_partner_prestashop(self, address, contact_type, parent):
        inv_zip = address.get("postcode", False)
        inv_city = address.get("city", False)
        inv_street = address.get("address1", False)
        inv_street2 = address.get("address2", False)
        inv_country_id = (
            self.env["res.country"]
            .search([("code", "=ilike", address.get("country_code", ""))], limit=1)
            .id
        )
        inv_state_id = (
            self.env["res.country.state"]
            .search(
                [
                    ("code", "=ilike", address.get("state_code", "")),
                    ("country_id", "=", inv_country_id),
                ],
                limit=1,
            )
            .id
        )
        inv_phone = address.get("phone_mobile", False)
        inv_name = "%s %s" % (
            address.get("firstname", False),
            address.get("lastname", False),
        )

        partner = self.filtered(
            lambda p: p.zip == inv_zip
            and p.city == inv_city
            and p.country_id.id == inv_country_id
            and p.name == inv_name
        )[:1]
        if not partner:
            partner = self.create(
                {
                    "name": inv_name,
                    "city": inv_city,
                    "street": inv_street,
                    "street2": inv_street2,
                    "phone": inv_phone,
                    "country_id": inv_country_id,
                    "state_id": inv_state_id,
                    "zip": inv_zip,
                    "type": contact_type,
                    "parent_id": parent.id,
                    "email": parent.email,
                }
            )
        else:
            partner.write(
                {
                    "type": contact_type,
                    "street": inv_street,
                    "street2": inv_street2,
                }
            )
        partner.onchange_country_lang()
        partner.extract_house_from_street()
        return partner, (self - partner)
