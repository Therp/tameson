
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError



class ModelName(models.Model):
    _name = 'helpdesk.ticket'
    _inherit = ['helpdesk.ticket', 'set.help.mixin']

    
