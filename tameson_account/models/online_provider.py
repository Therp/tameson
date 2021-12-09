# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from dateutil.relativedelta import relativedelta

import logging
_logger = logging.getLogger(__name__)


class OnlineBankStatementProvider(models.Model):
    _inherit = "online.bank.statement.provider"

    @api.model
    def _scheduled_pull(self):
        _logger.info("Scheduled pull of online bank statements...")

        providers = self.search(
            [("active", "=", True), ("next_run", "<=", fields.Datetime.now())]
        )
        if providers:
            _logger.info(
                "Pulling online bank statements of: %s"
                % ", ".join(providers.mapped("journal_id.name"))
            )
            for provider in providers.with_context({"scheduled": True}):
                # date_since = (
                #     (provider.last_successful_run)
                #     if provider.last_successful_run
                #     else (provider.next_run - provider._get_next_run_period())
                # )
                date_since = provider.next_run - provider._get_overlapped_run_period()
                date_until = provider.next_run
                if relativedelta(date_since, date_until).days > 10:
                    date_since = provider.next_run - provider._get_next_run_period()                    
                provider._pull(date_since, date_until)

        _logger.info("Scheduled pull of online bank statements complete.")

    def _get_overlapped_run_period(self):
        self.ensure_one()
        interval = self.interval_number * 3
        if self.interval_type == "minutes":
            return relativedelta(minutes=interval)
        elif self.interval_type == "hours":
            return relativedelta(hours=interval)
        elif self.interval_type == "days":
            return relativedelta(days=interval)
        elif self.interval_type == "weeks":
            return relativedelta(weeks=interval)
