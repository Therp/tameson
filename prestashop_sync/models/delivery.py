###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import fields, models


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    prestashop_carrier_ids = fields.One2many(
        string="Prestashop carrier ID",
        comodel_name="delivery.carrier.prestashop.id",
        inverse_name="carrier_id",
        index=True,
    )


class DeliveryCarrierPrestaId(models.Model):
    _name = "delivery.carrier.prestashop.id"
    _description = "Delivery Carrier Presta ID"

    _rec_name = "name"
    _order = "name ASC"

    name = fields.Char(string="Name", required=True, copy=False)
    carrier_id = fields.Many2one(
        string="Carrier",
        comodel_name="delivery.carrier",
        ondelete="restrict",
    )
