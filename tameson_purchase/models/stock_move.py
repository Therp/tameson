# Copyright 2020 Therp BV <https://therp.nl>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import models, fields


class StockMove(models.Model):
    _inherit = "stock.move"

    origin_so_picking_ids = fields.Many2many(
        "stock.picking",
        "associate_in_out",
        "associated_in",
        "associated_out",
        string="Origin SO picking",
        required=False,
        help="Outgoing pickings associated, to an incoming picking"
        "is set only for ungrouped lines deriving from sales orders",
    )
