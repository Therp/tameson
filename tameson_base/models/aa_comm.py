###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import api, fields, models


class AAComm(models.Model):
    _name = "aa.comm"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "ActiveAnts Communication"

    _rec_name = "name"
    _order = "name ASC"

    name = fields.Char()

    def get_search_string(self):
        return ""

    def mail_to_aa(self):
        composer_form_view_id = self.env.ref(
            "mail.email_compose_message_wizard_form"
        ).id
        template_id = (
            self.env["mail.template"]
            .search(
                [
                    ("name", "ilike", "ActiveAnts"),
                    ("name", "ilike", self.get_search_string()),
                ],
                limit=1,
            )
            .id
        )
        return {
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "mail.compose.message",
            "view_id": composer_form_view_id,
            "target": "new",
            "context": {
                "default_composition_mode": "comment",
                "default_res_id": self.ids[0],
                "default_model": self._name,
                "default_use_template": bool(template_id),
                "default_template_id": template_id,
                "active_ids": self.ids,
            },
        }

    @api.model
    def create(self, vals):
        partner = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("aa_mail_partner_id", default=0)
        )
        res = super().create(vals)
        res.message_subscribe(partner_ids=[int(partner)])
        return res
