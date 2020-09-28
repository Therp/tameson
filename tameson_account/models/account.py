from odoo import api, fields, models, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    t_comment = fields.Text(
        string=_('Comment'),
        required=False
    )

    @api.model
    def get_sale_order(self):
        if not self.invoice_origin:
            return

        try:
            return self.env['sale.order'].search([
                ['name', '=', self.invoice_origin],
            ])[0]
        except IndexError:
            pass


    def get_picking_ids(self):
        return self.mapped('line_ids').mapped('sale_line_ids').mapped('order_id').mapped('picking_ids')

class AccountPaymentTerm(models.Model):
    _inherit = 'account.payment.term'

    t_invoice_delivered_quantities = fields.Boolean(
        string=_('Invoice delivered quantities')
    )
