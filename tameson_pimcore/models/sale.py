###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from datetime import datetime

from dateutil.relativedelta import relativedelta

from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _get_sale_order_has_issues(self):
        vals = super(SaleOrder, self)._get_sale_order_has_issues()
        PimModel = self.env["pimcore.product.response"]
        PimLineModel = self.env["pimcore.product.response.line"]

        ## Check for full response within last 7 days, must be at least 1 from cron job
        full_pull = 7
        full_response = PimModel.search(
            [
                ("create_date", ">", datetime.now() - relativedelta(days=full_pull)),
                ("type", "=", "full"),
            ]
        )
        if not full_response:
            vals.append(
                {
                    "name": "Pimcore Full Response",
                    "orders": [(0, "Full import not found for last 7 days.")],
                }
            )
        ## Check for lines older than 1 day still not imported, must be imported (none in draft) everyday by cron
        draft_lines = PimLineModel.search(
            [
                ("create_date", "<", datetime.now() - relativedelta(days=1)),
                ("state", "=", "draft"),
            ]
        )
        ## Check for lines from previous day having error
        error_lines = PimLineModel.search(
            [
                ("state", "=", "error"),
                "|",
                ("create_date", ">", (datetime.now() - relativedelta(days=1)).date()),
                ("write_date", ">", (datetime.now() - relativedelta(days=1)).date()),
            ]
        )
        if draft_lines:
            vals.append(
                {
                    "name": "Pimcore Response Import",
                    "orders": [
                        (len(draft_lines), "Pimcore response data not imported")
                    ],
                }
            )
        if error_lines:
            vals.append(
                {
                    "name": "Pimcore Response Import Error",
                    "orders": [
                        (len(error_lines), "Pimcore Response Import failed for Error")
                    ],
                }
            )
        return vals
