###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import api, fields, models


class SetHelpModel(models.TransientModel):
    _name = "set.help.text"
    _description = "Set Help for Model"

    help = fields.Html()

    @api.model
    def default_get(self, fields):
        res = super(SetHelpModel, self).default_get(fields)
        model = self.env.context.get("active_model")
        help = self.env["ir.model"].search([("model", "=", model)], limit=1).help_text
        res["help"] = help
        return res

    def set_help_text(self):
        model = self.env.context.get("active_model")
        ir_model = self.env["ir.model"].search([("model", "=", model)], limit=1).sudo()
        ir_model.help_text = self.help
        return {"type": "ir.actions.act_window_close"}


class SetHelpMixin(models.AbstractModel):
    _name = "set.help.mixin"
    _description = "SetHelpMixin"

    help_text = fields.Html(compute="_get_help_text")

    def _get_help_text(self):
        model = (
            self.env["ir.model"].sudo().search([("model", "=", self._name)], limit=1)
        )
        for record in self:
            record.help_text = model.help_text

    def action_set_help(self):
        return {
            "name": "Set help %s" % self._name,
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "set.help.text",
            "target": "new",
        }
