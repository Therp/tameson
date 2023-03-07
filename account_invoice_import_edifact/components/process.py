# Copyright 2021 Camptocamp SA
# @author: Simone Orsi <simone.orsi@camptocamp.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


import logging

_logger = logging.getLogger(__name__)

from odoo.addons.component.core import Component


class EdiInvoiceProcess(Component):
    """Process sale orders."""

    _name = "edi.input.invoice.process"
    _inherit = "edi.component.input.mixin"
    _usage = "input.process"

    def process(self):
        wiz = self.env["account.invoice.import"].sudo().create({})
        wiz.invoice_file = self.exchange_record._get_file_content(binary=False)
        wiz.invoice_filename = self.exchange_record.exchange_filename
        name = self.exchange_record.backend_id.backend_type_id.name
        res = wiz.with_context(partner=name).import_invoice()
        if wiz.state == "update":
            res = wiz.with_context(partner=name).create_invoice_action_button()
