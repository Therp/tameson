from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    channable_api_base_url = fields.Char(string='Channable API base URL')

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        param_obj = self.env['ir.config_parameter'].sudo()
        res.update(
            channable_api_base_url=param_obj.get_param('channable_api_base_url', default='') or '',
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        param_obj = self.env['ir.config_parameter'].sudo()
        param_obj.set_param('channable_api_base_url', self.channable_api_base_url or '')
