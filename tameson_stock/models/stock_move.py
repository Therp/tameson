
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError



class StockMove(models.Model):
    _inherit = 'stock.move'

    
    def write(self, vals):
        moves = self.browse()
        propagated_date_field = False
        if vals.get('date_expected'):
            propagated_date_field = 'date_expected'
        elif vals.get('state', '') == 'done' and vals.get('date'):
            propagated_date_field = 'date'
        if propagated_date_field:
            new_date = fields.Datetime.to_datetime(vals.get(propagated_date_field))
            moves = self.filtered(lambda m: m.date_expected > new_date)
        res = super(StockMove, self).write(vals)
        for move in moves.mapped('move_dest_ids'):
            activity = move.picking_id.activity_ids.filtered(lambda a: a.automated and 'The scheduled date has been automatically updated due to a delay on' in a.note)
            if activity:
                activity.action_feedback(feedback="Scheduled on earlier date.")
        return res
