###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ShopifyInstanceEpt(models.Model):
    _name = "shopify.instance.ept"

    shopify_multipass_host = fields.Char(
        "Shop Address",
    )
    shopify_multipass_secret = fields.Char(
        "Multipass secret",
    )
    multipass_country_ids = fields.One2many(
        comodel_name="res.country",
        inverse_name="shopify_instance_id",
    )


class ResCountry(models.Model):
    _inherit = "res.country"

    shopify_instance_id = fields.Many2one(
        comodel_name="shopify.instance.ept",
        ondelete="restrict",
    )
