###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

import copy
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _name = "res.partner"
    _inherit = ["res.partner", "set.help.mixin"]

    t_partner_type_id = fields.Many2one(
        string="Partner type",
        comodel_name="tameson.partner.type",
        ondelete="restrict",
    )

    @api.constrains("email")
    def _check_email(self):
        if self.env.context.get("skip_email_check", False):
            return
        for record in self:
            if not record.parent_id and record.email:
                match = (
                    self.search(
                        [("email", "=", record.email), ("parent_id", "=", False)]
                    )
                    - self
                )
                if match:
                    raise ValidationError(
                        "Duplicate email for contact: %s" % match.name
                    )

    @api.constrains("child_ids", "is_company")
    def check_company_childs(self):
        if self.env.context.get("skip_child_check", True):
            return
        for record in self:
            if record.is_company and not any(record.child_ids.mapped("name")):
                raise ValidationError(
                    "At least one child contact with name needed for company contact."
                )

    def action_reset_password(self):
        return self.user_ids.sudo().action_reset_password()

    # @api.onchange('company_type')
    # def _onchange_company_type(self):
    #     if self.company_type == 'company':
    #         return {
    #             'warning': {
    #                 'title': 'Warning',
    #                 'message': 'At least one child contact with name needed for company contact.'
    #             }
    #         }

    def action_set_street(self):
        self._set_street()
        return True

    def extract_house_from_street(self):
        extract_pattern = r"(\d+)[\s/-]?(\w\s|\w$)?"
        unit_pattern = r"unit\W*\d+"
        for partner in self:
            split_success = False
            street = partner.street or ""
            unit_part = re.findall(unit_pattern, street, flags=re.IGNORECASE)
            if unit_part:
                street_number = False
                street_number2 = unit_part[0]
                street_name = re.compile(street_number2).sub("", street)
                split_success = True
            else:
                split_parts = re.findall(extract_pattern, street)
                if len(split_parts) == 1:
                    street_number = split_parts[0][0]
                    street_number2 = split_parts[0][1]
                    street_name = re.compile(extract_pattern).sub("", street)
                    split_success = True
            if split_success:
                partner.write(
                    {
                        "street_number": street_number,
                        "street_number2": street_number2,
                        "street_name": street_name,
                    }
                )
                partner.message_post(
                    body="House number extracted from address:\n%s" % street
                )

    @api.model_create_multi
    def create(self, vals_list):
        for val in vals_list:
            if val.get("vat", False) and val.get("parent_id", False):
                val["is_company"] = True
            if val.get("country_code", False):
                country_id = self.env["res.country"].search(
                    [("code", "=ilike", val["country_code"])], limit=1
                )
                val["country_id"] = country_id.id
                val.pop("country_code")
        partners = super().create(vals_list)
        return partners

    def write(self, vals):
        company_name = vals.get("company_name", False)
        if not self.parent_id and (vals.get("vat", False) or company_name):
            vals["is_company"] = True
        if company_name and not self.child_ids:
            child_vals = copy.deepcopy(vals)
            child_vals.update(
                {
                    "vat": False,
                    "company_name": False,
                    "is_company": False,
                    "child_ids": False,
                    "parent_id": self.id,
                }
            )
            self.sudo().create(child_vals)
            vals.update(
                {
                    "name": company_name,
                    "company_name": False,
                }
            )
        if vals.get("country_code", False):
            country_id = self.env["res.country"].search(
                [("code", "=ilike", vals["country_code"])], limit=1
            )
            vals["country_id"] = country_id.id
            vals.pop("country_code")
        return super().write(vals)
