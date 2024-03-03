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

    def get_so_ref(self):
        return ", ".join(
            self.mapped("invoice_line_ids.sale_line_ids.order_id")
            .filtered(lambda o: o.client_order_ref)
            .mapped("client_order_ref")
        )

    def send_invoice_mail(self):
        mail_template = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("auto_invoice_template_id", 0)
        )
        if not mail_template or not self:
            return
        for invoice in self.filtered(lambda inv: not inv.is_move_sent):
            invoice.with_context(force_send=True).message_post_with_template(
                mail_template,
                composition_mode="comment",
                email_layout_xmlid="mail.mail_notification_layout_with_responsible_signature",
            )
            invoice.write({"is_move_sent": True})

    def _post(self, soft=True):
        res = super()._post(soft=soft)
        for invoice in self:
            order = invoice.mapped("invoice_line_ids.sale_line_ids.order_id")[:1]
            if order and order.all_qty_delivered:
                invoice.send_invoice_mail()
        return res
