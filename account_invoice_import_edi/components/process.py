# Copyright 2021 Camptocamp SA
# @author: Simone Orsi <simone.orsi@camptocamp.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import _, api
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)

from odoo.addons.component.core import Component

class EDIExchangeInvoiceInput(Component):
    """Process sale orders."""

    _name = "edi.input.invoice.landefeld.process"
    _inherit = "edi.component.input.mixin"
    _usage = "input.process.invoice.landefeld"

    def process(self):
        wiz = self.env['account.invoice.import'].sudo().create({})
        wiz.invoice_file = self.exchange_record._get_file_content(binary=False)
        wiz.invoice_filename = self.exchange_record.exchange_filename
        res = wiz.import_invoice()