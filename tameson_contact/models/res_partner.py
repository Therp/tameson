
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

import re
from datetime import datetime

from odoo import models, fields, api, _, SUPERUSER_ID
from odoo.exceptions import ValidationError
from odoo.addons.base_address_extended.models.base_address_extended import STREET_FIELDS

class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'set.help.mixin']

    @api.model
    def _address_fields(self):
        res = super(ResPartner, self)._address_fields()
        res += STREET_FIELDS
        return res

    @api.constrains('email')
    def _check_email(self):
        if self.env.context.get('skip_email_check', False):
            return
        for record in self:
            if not record.parent_id and record.email:
                match = self.search([('email','=',record.email),('parent_id','=',False)]) - self
                if match:
                    raise ValidationError('Duplicate email for contact: %s' % match.name)

    @api.constrains('child_ids', 'is_company')
    def check_company_childs(self):
        if self.env.context.get('skip_child_check', False):
            return
        for record in self:
            if record.is_company and not any(record.child_ids.mapped('name')):
                raise ValidationError('At least one child contact with name needed for company contact.')

    
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

    @api.model
    def extract_house_from_street(self):
        extract_pattern = "(\d+)[\s/-]?(\w\s|\w$)?"
        for partner in self:
            if not partner.street_number:
                street = partner.street
                split_parts = re.findall(extract_pattern, street)
                if len(split_parts) == 1:
                    remaining_part = re.compile(extract_pattern).sub('', street)
                    partner.write({
                        'street_number': split_parts[0][0],
                        'street_number2': split_parts[0][1],
                        'street_name': remaining_part,
                    })
                    partner.message_post(body='House number extracted from address:\n%s' % street)
                else:
                    partner.activity_schedule('mail.mail_activity_data_warning', datetime.today().date(),
                note='House number extraction failed.', user_id=self.env.user.id or SUPERUSER_ID)
