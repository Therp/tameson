
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError



class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.constrains('email')
    def _check_email(self):
        for record in self:
            if record.email:
                child_ids = self.search([('id','child_of',record.parent_id.id or record.id)])
                match = self.search([('email','=',record.email),('id','not in',child_ids.ids)], limit=1)
                if match:
                    raise ValidationError('Duplicate email for contact: %s' % match.name)

    def action_set_street(self):
        self._set_street()
        return True