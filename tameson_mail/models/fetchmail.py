###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class IrMailServer(models.Model):
    _inherit = "fetchmail.server"

    def connect(self):
        try:
            connection = super().connect()
        except Exception as e:
            _logger.warn("SMTP Connect Error.", exc_info=True)
            raise e
        return connection
