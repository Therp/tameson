
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.osv import expression

class ProcurementGroup(models.Model):
    _inherit = 'procurement.group'


    @api.model
    def _get_moves_to_assign_domain(self):
        days = int(self.env["ir.config_parameter"].sudo().get_param("tameson_stock.auto_reservation_days", 7))
        return expression.AND([
            [('state', 'in', ['confirmed', 'partially_available'])],
            [('product_uom_qty', '!=', 0.0)],
            [('date_expected', '<=', (datetime.now() + relativedelta(days=days)).strftime(DEFAULT_SERVER_DATETIME_FORMAT))]
        ])
