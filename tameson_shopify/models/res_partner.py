###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import api, models


def get_vat_from_notes(notes):
    vat = False
    for item in notes:
        if item.get("name", "") == "VAT Registration Number":
            vat = item.get("value", False)
    return vat


def get_partner_vals(env, address, email):
    state_name = address.get("province")
    state_code = address.get("province_code")
    country = env["res.country"].search(
        [
            "|",
            ("name", "=", address.get("country")),
            ("code", "=", address.get("country_code")),
        ]
    )
    if not country:
        state = env["res.country.state"].search(
            ["|", ("code", "=", state_code), ("name", "=", state_name)], limit=1
        )
    else:
        state = env["res.country.state"].search(
            [
                "|",
                ("code", "=", state_code),
                ("name", "=", state_name),
                ("country_id", "=", country.id),
            ],
            limit=1,
        )
    partner_vals = {
        "name": address.get("name"),
        "street": address.get("address1"),
        "street2": address.get("address2"),
        "city": address.get("city"),
        "state_code": state_code,
        "state_name": state_name,
        "country_code": address.get("country_code"),
        "country_name": country,
        "phone": address.get("phone"),
        "email": email,
        "state_id": state.id or False,
        "zip": address.get("zip"),
        "country_id": country.id or False,
        "is_company": False,
    }
    return env["res.partner"]._prepare_partner_vals(partner_vals)


class ResPartner(models.Model):
    _inherit = "res.partner"

    def get_invoice_email(self):
        self.ensure_one()
        if self.parent_id:
            self = self.parent_id
        invoices = self.child_ids.filtered(
            lambda child: child.type == "invoice" and self.email != child.email
        )
        return invoices[:1].email or ""

    def _get_shopify_partner_data(self):
        self.ensure_one()
        tag_string = "odoo"
        if self.property_payment_term_id.t_invoice_delivered_quantities:
            tag_string = "ODOO-checkout, ODOO-invoice"
        elif self.property_product_pricelist.discount_policy == "without_discount":
            tag_string = "ODOO-checkout, ODOO-discount"
        else:
            tag_string = "odoo"
        return {
            "email": self.email,
            "return_to": "/",
            "first_name": self.name.split(" ")[0] if self.name else "",
            "last_name": " ".join(self.name.split(" ")[1:]) if self.name else "",
            "tag_string": tag_string,
            "identifier": self.id,
            "addresses": self._get_shopify_partner_address(),
        }

    def _get_shopify_partner_address(self):
        self.ensure_one()
        address = []
        childs = self.child_ids or self
        count = 1
        for child in childs:
            address.append(
                {
                    "address1": child.street,
                    "address2": (child.street2 or "") + "%d" % count,
                    "city": child.city,
                    "country": child.with_context(lang="en_US").country_id.name,
                    "first_name": child.name.split(" ")[0] if child.name else "",
                    "last_name": " ".join(child.name.split(" ")[1:])
                    if child.name
                    else "",
                    "company": child.parent_id.name or child.company_name or "",
                    "phone": child.phone,
                    "province": child.state_id.name or "",
                    "zip": child.zip,
                    "province_code": child.state_id.code or "",
                    "country_code": child.country_id.code,
                    "default": False,
                }
            )
            count += 1
        return address

    def shopify_get_contact_data(self):
        self.ensure_one()
        field_list = [
            "name",
            "street",
            "street2",
            "city",
            "phone",
            "email",
            "state_id",
            "zip",
            "country_id",
            "is_company",
            "vat",
        ]
        return ", ".join(
            [
                "%s: %s" % (item, val)
                for item, val in self.read(fields=field_list)[0].items()
            ]
        )

    def check_matching_contact(self, vals):
        return (
            self.name == vals["name"]
            and self.zip == vals["zip"]
            and self.city == vals["city"]
            and self.country_id.id == vals["country_id"]
            and self.email == vals["email"]
        )

    def shopify_get_adress(self, partner_vals, type):
        if self.is_company:
            contact = self.child_ids.filtered(lambda c: c.type == "contact")[:1]
            if not contact or not contact.check_matching_contact(partner_vals):
                contact = self.child_ids.filtered(lambda c: c.type == type)[:1]
                if contact:
                    if not contact.check_matching_contact(partner_vals):
                        partner_vals.update(type=contact.type, parent_id=self.id)
                        self.message_post(
                            body="Changed from: " + contact.shopify_get_contact_data()
                        )
                        contact.write(partner_vals)
                else:
                    partner_vals.update(type=type, parent_id=self.id)
                    contact = self.create(partner_vals)
        else:
            if self.check_matching_contact(partner_vals):
                contact = self
            else:
                contact = self.child_ids.filtered(lambda c: c.type == type)[:1]
                if contact:
                    if not contact.check_matching_contact(partner_vals):
                        self.message_post(
                            body="Changed from: " + contact.shopify_get_contact_data()
                        )
                        partner_vals.update(parent_id=self.id)
                        contact.write(partner_vals)
                else:
                    partner_vals.update(type=type, parent_id=self.id)
                    contact = self.create(partner_vals)
        return contact

    @api.model
    def create_or_update_customer(
        self,
        vals,
        log_book_id,
        is_company=False,
        parent_id=False,
        type=False,
        instance=False,
        email=False,
        customer_data_queue_line_id=False,
        order_data_queue_line=False,
    ):
        if customer_data_queue_line_id:
            contact = super(ResPartner, self).create_or_update_customer(
                vals,
                log_book_id,
                is_company,
                parent_id,
                type,
                instance,
                email,
                customer_data_queue_line_id,
                order_data_queue_line,
            )
        else:
            self = self.with_context(skip_child_check=True, skip_email_check=True)
            parent_id = self.browse(parent_id)
            company = False
            if type == "invoice":
                partner_vals = get_partner_vals(self.env, vals, email)
                invoice_email = vals.get("invoice_email", False)
                if invoice_email:
                    partner_vals.update(email=invoice_email)
                contact = parent_id.shopify_get_adress(partner_vals, type="invoice")
            elif type == "delivery":
                partner_vals = get_partner_vals(self.env, vals, email)
                contact = parent_id.shopify_get_adress(partner_vals, type="other")
            else:
                customer_vals = vals.get("customer", {})
                address = customer_vals.get("default_address", {})
                email = customer_vals.get("email", False)
                company = address.get("company", False)
                partner_vals = get_partner_vals(self.env, address, email)
                matched_contact = self.env["res.partner"].search(
                    [("email", "=", email), ("parent_id", "=", False)], limit=1
                )
                if company:
                    company_vals = partner_vals.copy()
                    company_vals.update(name=company, is_company=True)
                    if matched_contact:
                        partner_vals.update(
                            parent_id=matched_contact.id, type="contact"
                        )
                        contact = matched_contact.child_ids.filtered(
                            lambda c: c.type == "contact"
                        )[:1]
                        if contact:
                            if not contact.check_matching_contact(partner_vals):
                                matched_contact.message_post(
                                    body="Changed from: %s"
                                    % contact.shopify_get_contact_data()
                                )
                                contact.write(partner_vals)
                        else:
                            contact = self.create(partner_vals)
                        if not matched_contact.check_matching_contact(company_vals):
                            matched_contact.message_post(
                                body="Changed from: %s"
                                % matched_contact.shopify_get_contact_data()
                            )
                            matched_contact.write(company_vals)
                    else:
                        company_contact = self.create(company_vals)
                        partner_vals.update(
                            parent_id=company_contact.id, type="contact"
                        )
                        contact = self.create(partner_vals)
                        if (
                            company_contact.vat
                            and company_contact.country_id.country_group_ids.filtered(
                                lambda g: g.name == "Europe ex NL"
                            )
                        ):
                            company_contact.property_account_position_id = self.env[
                                "account.fiscal.position"
                            ].search([("name", "=", "EU landen")], limit=1)
                        elif not company_contact.country_id.country_group_ids.filtered(
                            lambda g: g.name == "Europe"
                        ):
                            company_contact.property_account_position_id = self.env[
                                "account.fiscal.position"
                            ].search([("name", "=", "Niet-EU landen")], limit=1)
                else:
                    if matched_contact:
                        contact = matched_contact
                        if not contact.check_matching_contact(partner_vals):
                            contact.message_post(
                                body="Changed from: "
                                + contact.shopify_get_contact_data()
                            )
                            contact.write(partner_vals)
                    else:
                        contact = self.create(partner_vals)
                contact.extract_house_from_street()
                if contact.parent_id:
                    contact.parent_id.extract_house_from_street()
            if not type:
                try:
                    wizard = (
                        self.env["portal.wizard"]
                        .with_context(active_ids=contact.ids)
                        .create({})
                    )
                    line = wizard.user_ids.filtered(lambda u: u.partner_id == contact)
                    if not line.in_portal:
                        line.write({"in_portal": True})
                        wizard.with_context(send_mail=False).action_apply()
                except:
                    pass
                vat = get_vat_from_notes(vals.get("note_attributes", []))
                if not vat:
                    vat = vals.get("metafields", {}).get("vat-id", False)
                if vat:
                    pcontact = contact.parent_id or contact
                    try:
                        pcontact.write({"vat": vat})
                    except Exception:
                        pcontact.write({"vat": False})

        return contact

    def get_tax_exempt(self):
        self.ensure_one()
        group = self.env.ref("__export__.europe_excluding_nl", False)
        return self.vat and group in self.country_id.country_group_ids
