from odoo import api, fields, models


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    channable_transporter_code = fields.Char(string="Channable Transporter Code", help="Transporter Code from Channable, to be used when an order is marked as shipped.")
