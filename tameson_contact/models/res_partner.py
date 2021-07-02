
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError



class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'set.help.mixin']

    @api.constrains('email')
    def _check_email(self):
        if self.env.context.get('skip_email_check', False):
            return
        for record in self:
            if record.email:
                child_ids = self.search([('id','child_of',record.parent_id.id or record.id)])
                match = self.search([('email','=',record.email),('id','not in',child_ids.ids)], limit=1)
                if match:
                    raise ValidationError('Duplicate email for contact: %s' % match.name)

    # @api.constrains('child_ids.name', 'is_company')
    # def check_company_childs(self):
    #     for record in self:
    #         if record.is_company and not any(record.child_ids.mapped('name')):
    #             raise ValidationError('At least one child contact with name needed for company contact.')

    
    @api.onchange('company_type')
    def _onchange_company_type(self):
        if self.company_type == 'company':
            return {
                'warning': {
                    'title': 'Warning',
                    'message': 'At least one child contact with name needed for company contact.'
                }
            }
    

    def action_set_street(self):
        self._set_street()
        return True