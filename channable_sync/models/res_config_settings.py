from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    channable_api_base_url = fields.Char(string='Channable API base URL')
    channable_orders_last_n_days_sync = fields.Integer(string="Field name", default=0)

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        param_obj = self.env['ir.config_parameter'].sudo()
        res.update(
            channable_api_base_url=param_obj.get_param('channable_api_base_url', default='') or '',
            channable_orders_last_n_days_sync=int(param_obj.get_param('channable_sync.orders_last_n_days_sync', default=0)) or 0,
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        param_obj = self.env['ir.config_parameter'].sudo()
        param_obj.set_param('channable_api_base_url', self.channable_api_base_url or '')
        param_obj.set_param('channable_sync.orders_last_n_days_sync', self.channable_orders_last_n_days_sync or 0)
