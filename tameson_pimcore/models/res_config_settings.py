from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    do_archive = fields.Selection(
        selection=[("0", "Disable"), ("1", "Enable")], default="1"
    )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        param_obj = self.env["ir.config_parameter"].sudo()
        res.update(
            do_archive=param_obj.get_param(
                "tameson_pimcore.product_archive", default="1"
            )
            or "1",
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        param_obj = self.env["ir.config_parameter"].sudo()
        param_obj.set_param("tameson_pimcore.product_archive", self.do_archive or "1")
