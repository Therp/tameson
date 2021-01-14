
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
from odoo.tools.misc import split_every


class ProcurementGroup(models.Model):
    _inherit = 'procurement.group'

    @api.model
    def _get_moves_to_assign_domain(self, company_id):
        days = int(self.env["ir.config_parameter"].sudo().get_param("tameson_stock.auto_reservation_days", 7))
        moves_domain =  super(ProcurementGroup, self)._get_moves_to_assign_domain(company_id)
        return expression.AND([moves_domain, [('date_expected', '<=', (datetime.now() + relativedelta(days=days)).strftime(DEFAULT_SERVER_DATETIME_FORMAT))]])

    @api.model
    def _run_scheduler_tasks(self, use_new_cursor=False, company_id=False):
        days = int(self.env["ir.config_parameter"].sudo().get_param("tameson_stock.auto_reservation_days", 7))
        moves_domain = [
            ('state', 'in', ['assigned', 'partially_available']),
            ('product_uom_qty', '!=', 0.0),
            ('date_expected', '>', (datetime.now() + relativedelta(days=days)).strftime(DEFAULT_SERVER_DATETIME_FORMAT))
        ]
        if company_id:
            moves_domain = expression.AND([[('company_id', '=', company_id)], moves_domain])
        moves_to_unreserve = self.env['stock.move'].search(moves_domain, limit=None,
            order='priority desc, date_expected asc')
        for moves_chunk in split_every(100, moves_to_unreserve.ids):
            self.env['stock.move'].browse(moves_chunk).sudo()._do_unreserve()
            if use_new_cursor:
                self._cr.commit()
        return super(ProcurementGroup, self)._run_scheduler_tasks(use_new_cursor, company_id)