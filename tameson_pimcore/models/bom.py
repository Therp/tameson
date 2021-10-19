# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError



class MrpBOM(models.Model):
    _inherit = 'mrp.bom'

    def get_bom_signature(self):
        self.ensure_one()
        return ','.join(self.bom_line_ids.mapped(lambda l: "%s,%.0f" % (l.product_id.default_code, l.product_qty)))