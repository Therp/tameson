
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
from dateutil.relativedelta import relativedelta


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _get_sale_order_has_issues(self):
        vals = super(SaleOrder, self)._get_sale_order_has_issues()
        PimModel = self.env['pimcore.product.response']
        PimLineModel = self.env['pimcore.product.response.line']

        ## Check for full response within last 7 days, must be at least 1 from cron job
        full_pull = 7
        full_response = PimModel.search([('create_date','>', datetime.now() - relativedelta(days=full_pull)), 
                                            ('type','=','full')])
        if not full_response:
            vals.append({
                'name': 'Pimcore Full Response',
                'orders': [(0,'Full response not found for last 7 days.')]
            })
        ## Check for lines older than 1 day still not imported, must be imported (none in draft) everyday by cron
        draft_lines = PimLineModel.search([('create_date','<', datetime.now() - relativedelta(days=1)), 
                                            ('state','=','draft')])
        if draft_lines:
            vals.append({
                'name': 'Pimcore Response Import',
                'orders': [(len(draft_lines),'Pimcore response data not imported')]
            })
        return vals

