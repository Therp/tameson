from odoo import api, fields, models, _


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    presta_ups_access_point_id = fields.Char(
        required=False,
        string='UPS Access Point ID'
    )
    presta_ups_access_point_country = fields.Char(
        required=False,
        string='UPS Access Point Country Code'
    )
    presta_ups_ap_data_copied_from_so = fields.Boolean(
        required=True,
        default=False
    )

    @api.model
    def create(self, values):
        values = values or {}

        so = self._get_so(values.get('origin', False))
        if so and so.presta_ups_access_point_id and not values.get('presta_ups_access_point_id'):
            values['presta_ups_access_point_id'] = so.presta_ups_access_point_id
            values['presta_ups_ap_data_copied_from_so'] = True
        if so and (so.presta_ups_access_point_id or values.get('presta_ups_access_point_id')) and not values.get('presta_ups_access_point_country'):
            values['presta_ups_access_point_country'] = so._guess_access_point_country()
            values['presta_ups_ap_data_copied_from_so'] = True

        return super(StockPicking, self).create(values)

    def write(self, vals):
        result = super(StockPicking, self).write(vals)

        for rec in self:
            so = rec._get_so(rec.origin)
            if so and not rec.presta_ups_ap_data_copied_from_so:
                rec.presta_ups_ap_data_copied_from_so = True
                if not rec.presta_ups_access_point_id:
                    rec.presta_ups_access_point_id = so.presta_ups_access_point_id
                if not rec.presta_ups_access_point_country and rec.presta_ups_access_point_id:
                    rec.presta_ups_access_point_country = so._guess_access_point_country()

        return result

    def get_access_point_id(self):
        if self.presta_ups_access_point_id:
            return self.presta_ups_access_point_id

        so = self._get_so()
        if so:
            return so.presta_ups_access_point_id

    def get_access_point_country(self):
        if self.presta_ups_access_point_country:
            return self.presta_ups_access_point_country

        so = self._get_so()
        if so:
            return so._guess_access_point_country()

    def _get_so(self, name=None):
        if not name:
            name = self.origin

        try:
            return self.env['sale.order'].search([
                ['name', '=', name],
            ])[0]
        except IndexError:
            pass
