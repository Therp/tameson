###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import fields, models


class Website(models.Model):
    _inherit = "website"

    gtag_key = fields.Char()

    def get_open_orders(self):
        orders = self.env["sale.order"].sudo()
        if not self.env.user._is_public():
            partner = self.env.user.partner_id
            domain = [
                ("message_partner_ids", "child_of", [partner.commercial_partner_id.id]),
                ("state", "in", ["draft", "sent"]),
            ]
            orders = orders.search(domain, limit=10, order="create_date DESC")
        return orders
