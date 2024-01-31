###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import api, fields, models


class ContactCreationWizard(models.TransientModel):
    _name = "contact.creation.wizard"
    _description = "Contact Creation Wizard"

    name = fields.Char(required=True)
    is_individual = fields.Boolean(default=False)
    company_name = fields.Char()
    street = fields.Char()
    street2 = fields.Char()
    no_house = fields.Boolean(default=False)
    house = fields.Char()
    city = fields.Char()
    zip_code = fields.Char()
    country = fields.Many2one(
        comodel_name="res.country",
        ondelete="restrict",
    )
    state = fields.Many2one(
        comodel_name="res.country.state",
        ondelete="restrict",
    )
    phone = fields.Char()
    email = fields.Char()
    vat = fields.Char("VAT")
    shipping_street = fields.Char()
    shipping_street2 = fields.Char()
    shipping_house = fields.Char()
    shipping_city = fields.Char()
    shipping_zip_code = fields.Char()
    shipping_email = fields.Char()
    invoice_street = fields.Char()
    invoice_street2 = fields.Char()
    invoice_house = fields.Char()
    invoice_city = fields.Char()
    invoice_email = fields.Char()
    invoice_zip_code = fields.Char()
    vat_required = fields.Boolean(compute="get_vat_required")
    vat_bypass = fields.Boolean("VAT Bypass")

    @api.depends("country", "is_individual")
    def get_vat_required(self):
        country_ids = self.env.ref("__export__.europe_excluding_nl").country_ids.ids
        for record in self:
            record.vat_required = (
                not record.is_individual and record.country.id in country_ids
            )

    def action_create(self):
        partner_data = {
            "name": self.name,
            "is_company": False,
            "street_number": self.house,
            "street_name": self.street,
            "street2": self.street2,
            "city": self.city,
            "zip": self.zip_code,
            "country_id": self.country.id,
            "state_id": self.state.id,
            "email": self.email,
            "phone": self.phone,
            "vat": self.vat,
            "child_ids": [],
            "lang": False,
        }
        if not self.is_individual:
            child_contact = partner_data.copy()
            childs = partner_data.get("child_ids") + [(0, 0, child_contact)]
            partner_data.update(
                {
                    "name": self.company_name,
                    "is_company": True,
                    "child_ids": childs,
                    "vat": False,
                }
            )
        if self.shipping_street or self.shipping_email:
            shipping_contact = {
                "name": self.name,
                "is_company": False,
                "street_number": self.shipping_house or self.house,
                "street_name": self.shipping_street or self.street,
                "street2": self.shipping_street2 or self.street2,
                "city": self.shipping_city or self.city,
                "zip": self.shipping_zip_code or self.zip_code,
                "country_id": self.country.id,
                "state_id": self.state.id,
                "email": self.shipping_email or self.email,
                "phone": self.phone,
                "type": "delivery",
                "lang": False,
            }
            childs = partner_data.get("child_ids") + [(0, 0, shipping_contact)]
            partner_data.update({"child_ids": childs})
        if self.invoice_street or self.invoice_email:
            invoice_contact = {
                "name": self.name,
                "is_company": False,
                "street_number": self.invoice_house or self.house,
                "street_name": self.invoice_street or self.street,
                "street2": self.invoice_street2 or self.street2,
                "city": self.invoice_city or self.city,
                "zip": self.invoice_zip_code or self.zip_code,
                "country_id": self.country.id,
                "state_id": self.state.id,
                "email": self.invoice_email or self.email,
                "phone": self.phone,
                "type": "invoice",
                "lang": False,
            }
            childs = partner_data.get("child_ids") + [(0, 0, invoice_contact)]
            partner_data.update({"child_ids": childs})
        self.env["res.partner"].create(partner_data)
