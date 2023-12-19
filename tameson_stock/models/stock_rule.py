###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from datetime import datetime

from dateutil.relativedelta import relativedelta

from odoo import api, models
from odoo.osv import expression
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.misc import split_every

# Function: unreserve stock moves that lie 'auto_reservation_days'
# days in the future,  after that reserve moves that are within
# now till that date
# Reason: ODOO normally reserves from stock-on-hand without
# taking into account future incoming stock moves that are not
# done yet, this can lead to stock moves not being reserved when
#  an incoming move qty covers an outgoing move qty at a later
# date. As we have our min_qty field that already takes into
# account the allowed amount that can be sold, this solves
# the issue of moves not being reserved while they should be.


class ProcurementGroup(models.Model):
    _inherit = "procurement.group"

    @api.model
    def _get_moves_to_assign_domain(self, company_id):
        days = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("tameson_stock.auto_reservation_days", 7)
        )
        moves_domain = super(ProcurementGroup, self)._get_moves_to_assign_domain(
            company_id
        )
        new_domain = [
            "|",
            (
                "date",
                "<=",
                (datetime.now() + relativedelta(days=days)).strftime(
                    DEFAULT_SERVER_DATETIME_FORMAT
                ),
            ),
            ("picking_move_type", "=", "direct"),
        ]
        return expression.AND([moves_domain, new_domain])

    @api.model
    def _run_scheduler_tasks(self, use_new_cursor=False, company_id=False):
        days = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("tameson_stock.auto_reservation_days", 7)
        )
        moves_domain = [
            ("state", "in", ["assigned", "partially_available"]),
            ("product_uom_qty", "!=", 0.0),
            (
                "date",
                ">",
                (datetime.now() + relativedelta(days=days)).strftime(
                    DEFAULT_SERVER_DATETIME_FORMAT
                ),
            ),
            ("picking_code", "=", "outgoing"),
            ("picking_move_type", "!=", "direct"),
        ]
        if company_id:
            moves_domain = expression.AND(
                [[("company_id", "=", company_id)], moves_domain]
            )
        moves_to_unreserve = self.env["stock.move"].search(
            moves_domain, limit=None, order="priority desc, date_expected asc"
        )
        for moves_chunk in split_every(100, moves_to_unreserve.ids):
            self.env["stock.move"].browse(moves_chunk).sudo()._do_unreserve()
            if use_new_cursor:
                self._cr.commit()
        return super(ProcurementGroup, self)._run_scheduler_tasks(
            use_new_cursor, company_id
        )
