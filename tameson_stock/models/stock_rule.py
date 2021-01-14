
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
    def _get_moves_to_assign_domain(self, company_id):
        days = int(self.env["ir.config_parameter"].sudo().get_param("tameson_stock.auto_reservation_days", 7))
        moves_domain =  super(ProcurementGroup, self)._get_moves_to_assign_domain(company_id)
        return expression.AND([moves_domain, [('date_expected', '<=', (datetime.now() + relativedelta(days=days)).strftime(DEFAULT_SERVER_DATETIME_FORMAT))]])
