###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import _, fields, models


def get_selection_label(self, object, field_name, field_value):
    return _(
        dict(
            self.env[object].fields_get(allfields=[field_name])[field_name]["selection"]
        )[field_value]
    )


class ResPartner(models.Model):
    _inherit = "res.partner"

    def can_edit_vat(self):
        if not (self.vat or self.parent_id):
            return True
        else:
            return super(ResPartner, self).can_edit_vat()

    type_name = fields.Char(compute="_get_type_name")

    def _get_type_name(self):
        for record in self:
            record.type_name = get_selection_label(
                record, "res.partner", "type", record.type
            )

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
                    "address2": (child.street2 or ""),
                    "city": child.city,
                    "country": child.with_context(lang="en_US").country_id.name,
                    "first_name": child.name.split(" ")[0] if child.name else "",
                    "last_name": (
                        " ".join(child.name.split(" ")[1:]) if child.name else ""
                    )
                    + "(%d)" % count,
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

    def get_tax_exempt(self):
        self.ensure_one()
        group = self.env.ref("__export__.europe_excluding_nl", False)
        return bool(self.vat and group in self.country_id.country_group_ids)

    def get_customer_metafield_data(self):
        self.ensure_one()
        odoo_te = self.get_tax_exempt()
        odoo_invoice_email = self.get_invoice_email()
        return [
            {
                "tax_exempt": odoo_te,
                "invoice_email": odoo_invoice_email,
                "vat": self.vat,
            }
        ]
