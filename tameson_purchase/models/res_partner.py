# -*- coding: utf-8 -*-
# Copyright 2020 Therp BV <https://therp.nl>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    no_grouping_po_lines = fields.Boolean()
