###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import api, fields, models


class ModelName(models.Model):
    _name = "helpdesk.ticket"
    _inherit = ["helpdesk.ticket", "set.help.mixin"]

    any_non_returnable = fields.Boolean(related="sale_order_id.any_non_returnable")
    non_returnable_skus = fields.Char(related="sale_order_id.non_returnable_skus")
    restock_fee_limit_warning = fields.Boolean(compute="_compute_restock_fee_limit")
    restock_fee_limit = fields.Char(compute="_compute_restock_fee_limit")
    aa_comm_id = fields.Many2one(
        string="AA Communication",
        comodel_name="aa.comm",
        ondelete="restrict",
        readonly=True,
    )

    def action_mail_to_customer(self):
        composer_form_view_id = self.env.ref(
            "mail.email_compose_message_wizard_form"
        ).id
        template_id = (
            self.env["mail.template"]
            .sudo()
            .search([("model_id.model", "=", self._name)], limit=1)
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
                "default_model": "helpdesk.ticket",
                "default_use_template": bool(template_id),
                "default_template_id": template_id,
                "active_ids": self.ids,
            },
        }

    def action_mail_to_aa(self):
        composer_form_view_id = self.env.ref(
            "mail.email_compose_message_wizard_form"
        ).id
        template_id = (
            self.env["mail.template"]
            .search([("name", "ilike", "ActiveAnts")], limit=1)
            .id
        )
        return {
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "mail.compose.message",
            "view_id": composer_form_view_id,
            "target": "new",
            "context": {
                "default_composition_mode": "mass_mail",
                "default_res_id": self.ids[0],
                "default_model": "helpdesk.ticket",
                "default_use_template": bool(template_id),
                "default_template_id": template_id,
                "active_ids": self.ids,
            },
        }

    def _compute_restock_fee_limit(self):
        restock_fee_limit = (
            self.env["ir.config_parameter"].sudo().get_param("restock_fee_limit", 0)
        )
        limit = float(restock_fee_limit)
        for record in self:
            if (
                limit > 1
                and record.sale_order_id
                and record.sale_order_id.amount_total >= limit
            ):
                record.restock_fee_limit_warning = True
                record.restock_fee_limit = restock_fee_limit
            else:
                record.restock_fee_limit_warning = False
                record.restock_fee_limit = ""

    def action_reship(self):
        view = self.env.ref("tameson_helpdesk.view_stock_picking_reship")
        action = self.env.ref("stock.act_stock_return_picking").read()[0]
        action.update(
            {
                "views": [(view.id, "form")],
                "name": "Reship Delivery",
                "display_name": "Reship Delivery",
            }
        )
        return action

    @api.model_create_multi
    def create(self, list_value):
        res = super().create(list_value)
        for rec in res:
            rec.aa_comm_id = self.env["aa.comm"].create(
                {
                    "name": rec.name,
                    "ticket_id": rec.id,
                }
            )
        return res


class AAComm(models.Model):
    _inherit = "aa.comm"

    ticket_id = fields.Many2one(
        comodel_name="helpdesk.ticket",
        ondelete="restrict",
    )

    def get_search_string(self):
        if self.ticket_id:
            return "ticket"
        else:
            return super().get_search_string()
