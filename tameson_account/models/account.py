from odoo import _, api, fields, models
from odoo.tools.misc import format_date


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def remove_move_reconcile(self):
        self_sudo = self.sudo()
        return super(AccountMoveLine, self_sudo).remove_move_reconcile()


class AccountMove(models.Model):
    _name = "account.move"
    _inherit = ["account.move", "set.help.mixin"]

    invoice_outstanding_credits_debits_widget = fields.Text(groups="account.group_account_invoice,sales_team.group_sale_salesman",
        compute_sudo=True)
    invoice_payments_widget = fields.Text(groups="account.group_account_invoice,sales_team.group_sale_salesman",
        compute_sudo=True)
    invoice_has_outstanding = fields.Boolean(groups="account.group_account_invoice,sales_team.group_sale_salesman", 
        compute_sudo=True)

    t_comment = fields.Text(string=_("Comment"), required=False)
    restock_fee_limit_warning = fields.Boolean(compute="_get_restock_fee_limit")
    restock_fee_limit = fields.Char(compute="_get_restock_fee_limit")

    def js_assign_outstanding_line(self, line_id):
        self_sudo = self.sudo()
        return super(AccountMove, self_sudo).js_assign_outstanding_line(line_id)
    
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

    def action_register_payment_direct(self, journal_id=False):
        if self.state == "draft":
            self.action_post()
        payment_env = self.env["account.payment"].with_context(
            active_ids=self.ids, active_model=self._name
        )
        payment_vals = payment_env.default_get(list(payment_env.fields_get()))

        if not journal_id:
            journal_id = (
                self.env["account.journal"]
                .search([("type", "in", ("bank", "cash"))], limit=1)
                .id
            )

        payment_vals.update({"journal_id": journal_id})
        payment_new = payment_env.new(payment_vals)
        payment_new._onchange_journal()
        payment_new._onchange_partner_id()
        payment_new._onchange_payment_type()
        payment_new._onchange_amount()
        payment_new._onchange_currency()
        payment_vals = payment_new._convert_to_write(
            {name: payment_new[name] for name in payment_new._cache}
        )
        payment = self.env["account.payment"].create(payment_vals)
        payment.post()

    def button_draft(self):
        user = self.env.user
        if user.has_group("sales_team.group_sale_salesman") or user.has_group(
            "purchase.group_purchase_user"
        ):
            self = self.sudo()
        return super(AccountMove, self).button_draft()

    def action_post(self):
        user = self.env.user
        if user.has_group("sales_team.group_sale_salesman") or user.has_group(
            "purchase.group_purchase_user"
        ):
            self = self.sudo()
        return super(AccountMove, self).action_post()

    def action_invoice_register_payment(self):
        user = self.env.user
        if user.has_group("sales_team.group_sale_salesman") or user.has_group(
            "purchase.group_purchase_user"
        ):
            self = self.sudo()
        return super(AccountMove, self).action_invoice_register_payment()

    def button_cancel(self):
        user = self.env.user
        if user.has_group("sales_team.group_sale_salesman") or user.has_group(
            "purchase.group_purchase_user"
        ):
            self = self.sudo()
        return super(AccountMove, self).button_cancel()


class AccountPaymentTerm(models.Model):
    _inherit = "account.payment.term"

    t_invoice_delivered_quantities = fields.Boolean(
        string=_("Invoice delivered quantities")
    )


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    def reverse_moves(self):
        user = self.env.user
        if user.has_group("sales_team.group_sale_salesman") or user.has_group(
            "purchase.group_purchase_user"
        ):
            self = self.sudo()
        return super(AccountMoveReversal, self).reverse_moves()


class AccountReconciliation(models.AbstractModel):
    _inherit = "account.reconciliation.widget"

    @api.model
    def _prepare_move_lines(
        self, move_lines, target_currency=False, target_date=False, recs_count=0
    ):
        res = super(AccountReconciliation, self)._prepare_move_lines(
            move_lines,
            target_currency=target_currency,
            target_date=target_date,
            recs_count=recs_count,
        )
        for line in res:
            if line["ref"]:
                invoice = self.env["account.move"].search(
                    [("name", "=", line["ref"])], limit=1
                )
                if invoice.invoice_date:
                    line["ref"] += " - Inv. Date: %s" % format_date(
                        self.env, invoice.invoice_date
                    )
        return res
