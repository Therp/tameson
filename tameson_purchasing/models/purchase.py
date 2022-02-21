from odoo import api, fields, models, _
from odoo.tools import float_compare, float_is_zero


class PurchaseOrder(models.Model):
    _name= 'purchase.order'
    _inherit = ['purchase.order', 'set.help.mixin']


    t_purchase_method = fields.Selection(
        [
            ('purchase', 'Ordered quantities'),
            ('receive', 'Delivered quantities'),
        ],
        string=_('Control Policy (overrides product control policies)'),
        default='purchase',
        required=True,
    )

    t_done_pickings = fields.Many2many(
        'stock.picking',
        string=_('Done pickings for this purchase order'),
        compute='_compute_t_done_pickings'
    )

    t_clipboard_text_handle = fields.Char(
        string="Products Quantity (Clipboard)",
        compute="_compute_clipboard_text_handle",
    )


    ## compute invoice_status based on t_purchase_method instead of each product purchase_method
    @api.depends('state', 'order_line.qty_invoiced', 'order_line.qty_received', 'order_line.product_qty', 't_purchase_method')
    def _get_invoiced(self):
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for order in self:
            if order.state not in ('purchase', 'done'):
                order.invoice_status = 'no'
                continue

            if any(
                float_compare(
                    line.qty_invoiced,
                    line.product_qty if order.t_purchase_method == 'purchase' else line.qty_received,
                    precision_digits=precision,
                )
                == -1
                for line in order.order_line.filtered(lambda l: not l.display_type)
            ):
                order.invoice_status = 'to invoice'
            elif (
                all(
                    float_compare(
                        line.qty_invoiced,
                        line.product_qty if order.t_purchase_method == "purchase" else line.qty_received,
                        precision_digits=precision,
                    )
                    >= 0
                    for line in order.order_line.filtered(lambda l: not l.display_type)
                )
                and order.invoice_ids
            ):
                order.invoice_status = 'invoiced'
            else:
                order.invoice_status = 'no'

    def _compute_clipboard_text_handle(self):
        for po in self:
            text_val_to_clipboard = "/"
            for po_line in po.order_line:
                supplier_rec = po_line.product_id.seller_ids.filtered(
                    lambda v: v.name == po.partner_id
                )
                if supplier_rec and supplier_rec[0].product_code:
                    product_code = supplier_rec[0].product_code
                else:
                    product_code = po_line.product_id.default_code
                qty = str(po_line.product_qty)
                text_val_to_clipboard = (
                    text_val_to_clipboard + "{prod_qty}\t{prod_code}\n".format(
                        prod_qty=qty, prod_code=product_code
                    )
                )
            po.t_clipboard_text_handle = text_val_to_clipboard

    def tameson_po_copy_clipboard(self):
        pass

    @api.onchange('partner_id')
    def _onchange_partner_id_change_t_purchase_method(self):
        for r in self:
            if r.partner_id:
                term_id = r.partner_id.property_supplier_payment_term_id
                if term_id:
                    if term_id.t_invoice_delivered_quantities:
                        r.t_purchase_method = 'receive'
                    else:
                        r.t_purchase_method = 'purchase'
                else:
                    r.t_purchase_method = 'purchase'

    @api.depends('picking_ids.state')
    def _compute_t_done_pickings(self):
        for r in self:
            r.t_done_pickings = r.picking_ids.filtered(
                lambda picking: picking.state == 'done'
            )

    def _create_invoice(self, send_email=True):
        if self.invoice_status == 'invoiced':
            return

        invoice_ids = set(self.invoice_ids.ids)

        view = self.with_context(create_bill=True).action_view_invoice()
        #  {'default_type': 'in_invoice', 'default_company_id': 1, 'default_purchase_id': 41, 'default_invoice_origin': 'P00039', 'default_ref': False},
        ctx = view['context']
        vals = {}
        for k, v in ctx.items():
            if k.startswith('default_'):
                fname = k.replace('default_', '')
                vals[fname] = v
        inv = self.env['account.move'].new(vals)
        inv.purchase_id = self
        inv._onchange_purchase_auto_complete()
        vals = {}

        for fname, f in inv._fields.items():
            try:
                v = f.convert_to_write(getattr(inv, fname), inv)
                vals[fname] = v
            except TypeError:  # error for NewId, skip such fields, TODO maybe there's a better way
                continue
        inv.create(vals)

        new_invoice_ids = self.invoice_ids.filtered(
            lambda inv: inv.id not in invoice_ids
        )
        new_invoice_ids.action_post()

        if send_email:
            view_data = new_invoice_ids.with_context(
                active_id=self.id,
                active_ids=self.ids,
                active_model='purchase.order',
                default_invoice_origin=self.name,
                default_partner_id=self.partner_id.id,
            ).action_invoice_sent()
            ctx = dict(
                active_ids=new_invoice_ids.ids,
                **view_data['context']
            )
            send_id = self.env[view_data['res_model']].with_context(**ctx).create({
                'composition_mode': 'comment',
                'invoice_ids': [(6, None, new_invoice_ids.ids)],
                'is_email': True,
                'partner_id': self.partner_id.id,
                'template_id': ctx['default_template_id'],
            })
            # This is to trigger template_id change, to fill in template's
            # subject and body
            send_id.onchange_template_id()
            print_data = send_id.with_context(**ctx).send_and_print_action()
            report = self.env['ir.actions.report'].sudo().search([
                ['report_file', '=', print_data['report_file']],
                ['report_name', '=', print_data['report_name']],
                ['report_type', '=', print_data['report_type']],
            ])
            report.render_qweb_pdf(new_invoice_ids.ids)


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    t_purchase_method = fields.Selection(
        [
            ('purchase', 'Ordered quantities'),
            ('receive', 'Delivered quantities'),
        ],
        string=_('Control Policy (overrides product control policies)'),
        compute='_get_t_purchase_method'
    )

    @api.depends('order_id.t_purchase_method', 'product_id.purchase_method', 'product_id.type')
    def _get_t_purchase_method(self):
        for line in self:
            if line.product_id.type == 'product':
                line.t_purchase_method = line.order_id.t_purchase_method or line.product_id.purchase_method
            else:
                line.t_purchase_method = line.product_id.purchase_method

    # Some overrides for Odoo base code
    # SO-44999: use t_purchase_method instead of product_id.purchase_method
    def _prepare_account_move_line(self, move):
        self.ensure_one()
        if self.t_purchase_method == 'purchase':
            qty = self.product_qty - self.qty_invoiced
        else:
            qty = self.qty_received - self.qty_invoiced
        if float_compare(qty, 0.0, precision_rounding=self.product_uom.rounding) <= 0:
            qty = 0.0

        if self.currency_id == move.company_id.currency_id:
            currency = False
        else:
            currency = move.currency_id

        return {
            'name': '%s: %s' % (self.order_id.name, self.name),
            'move_id': move.id,
            'currency_id': currency and currency.id or False,
            'purchase_line_id': self.id,
            'date_maturity': move.invoice_date_due,
            'product_uom_id': self.product_uom.id,
            'product_id': self.product_id.id,
            'price_unit': self.price_unit,
            'quantity': qty,
            'partner_id': move.partner_id.id,
            'analytic_account_id': self.account_analytic_id.id,
            'analytic_tag_ids': [(6, 0, self.analytic_tag_ids.ids)],
            'tax_ids': [(6, 0, self.taxes_id.ids)],
            'display_type': self.display_type,
        }
