
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta



class StockMove(models.Model):
    _inherit = 'stock.move'
    
    def write(self, vals):
        propagated_date_field = False
        if vals.get('date_expected'):
            propagated_date_field = 'date_expected'
        elif vals.get('state', '') == 'done' and vals.get('date'):
            propagated_date_field = 'date'
        new_date = fields.Datetime.to_datetime(vals.get(propagated_date_field))
        res = super(StockMove, self).write(vals)
        ## Compare new date on Incoming operation with SO delivery/expected date
        ## Dismiss exception posted on Picking if not later than SO delivery/expected date + propagate_date_minimum_delta
        ## also dismiss manual date change exception if any
        if propagated_date_field:
            for move in self.mapped('move_dest_ids'):
                auto_activity = move.picking_id.activity_ids.filtered(lambda a: a.automated and 'The scheduled date has been automatically updated due to a delay on' in a.note)
                order_date = (move.picking_id.sale_id.commitment_date or move.picking_id.sale_id.expected_date) + relativedelta(days=self[:1].propagate_date_minimum_delta)
                if auto_activity and new_date <= order_date:
                    auto_activity.action_feedback(feedback="Scheduled on earlier date.")
                manu_activity = move.picking_id.activity_ids.filtered(lambda a: a.automated and 'The scheduled date should be updated due to a delay on' in a.note)
                if manu_activity:
                    manu_activity.action_feedback(feedback="Scheduled on earlier date.")
        ## end
        return res
