###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import api, fields, models


@api.model
def _lang_get(self):
    return self.env["res.lang"].get_installed()


class ResCountry(models.Model):
    _inherit = "res.country"

    select_lang = fields.Selection(
        _lang_get,
        string="Default Language",
    )
    select_pricelist_id = fields.Many2one(
        string="Default Pricelist",
        comodel_name="product.pricelist",
        ondelete="restrict",
    )
    customer_note = fields.Text()
