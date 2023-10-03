from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def remove_move_reconcile(self):
        self_sudo = self.sudo()
        return super(AccountMoveLine, self_sudo).remove_move_reconcile()


class AccountMove(models.Model):
    _inherit = "account.move"
    # _name = "account.move"
    # _inherit = ["account.move", "set.help.mixin"]

    restock_fee_limit_warning = fields.Boolean(compute="_get_restock_fee_limit")
    restock_fee_limit = fields.Char(compute="_get_restock_fee_limit")

    def _get_restock_fee_limit(self):
        restock_fee_limit = (
            self.env["ir.config_parameter"].sudo().get_param("restock_fee_limit", 0)
        )
        limit = float(restock_fee_limit)
        for record in self:
            if limit > 1 and record.amount_total >= limit:
                record.restock_fee_limit_warning = True
                record.restock_fee_limit = restock_fee_limit
            else:
                record.restock_fee_limit_warning = False
                record.restock_fee_limit = ""

    @api.model
    def get_sale_order(self):
        if not self.invoice_origin:
            return
        return self.env["sale.order"].search(
            [("name", "=", self.invoice_origin)], limit=1
        )

    def get_picking_ids(self):
        return self.mapped("line_ids.sale_line_ids.order_id.picking_ids")

    # def action_register_payment_direct(self, journal_id=False):
    #     if self.state == "draft":
    #         self.action_post()
    #     payment_env = self.env["account.payment"].with_context(
    #         active_ids=self.ids, active_model=self._name
    #     )
    #     payment_vals = payment_env.default_get(list(payment_env.fields_get()))

    #     if not journal_id:
    #         journal_id = (
    #             self.env["account.journal"]
    #             .search([("type", "in", ("bank", "cash"))], limit=1)
    #             .id
    #         )

    #     payment_vals.update({"journal_id": journal_id})
    #     payment_new = payment_env.new(payment_vals)
    #     payment_new._onchange_journal()
    #     payment_new._onchange_partner_id()
    #     payment_new._onchange_payment_type()
    #     payment_new._onchange_amount()
    #     payment_new._onchange_currency()
    #     payment_vals = payment_new._convert_to_write(
    #         {name: payment_new[name] for name in payment_new._cache}
    #     )
    #     payment = self.env["account.payment"].create(payment_vals)
    #     payment.post()
