from odoo import api, fields, models, _
from odoo.tools import float_compare, float_is_zero


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    presta_ups_access_point_id = fields.Char(
        required=False,
        string='UPS Access Point ID'
    )
    presta_ups_access_point_country = fields.Char(
        required=False,
        string='UPS Access Point Country Code'
    )

    def _guess_access_point_country(self):
        if self.presta_ups_access_point_country:
            return self.presta_ups_access_point_country
        if not self.presta_ups_access_point_id:
            return
        if not self.partner_id or not self.partner_id.country_id:
            return
        return self.partner_id.country_id.code
