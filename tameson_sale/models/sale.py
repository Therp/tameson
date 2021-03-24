import base64

from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError
from odoo.tools import formataddr, float_compare, float_is_zero

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    t_done_pickings = fields.Many2many(
        'stock.picking',
        string=_('Done pickings for this sale order'),
        compute='_compute_t_done_pickings'
    )
    t_is_paid = fields.Boolean(
        compute='_get_t_is_paid',
        string=_('Is order paid?'),
        readonly=True,
        store=True
    )
    t_invoice_policy = fields.Selection(
        [
            ('order', 'Ordered quantities'),
            ('delivery', 'Delivered quantities'),
            ('cost', 'Invoice based on time and material')
        ],
        string=_('Invoicing Policy (overrides product invoice policies)'),
        default=None,
    )
    t_is_delivery_invoice_policy = fields.Boolean(
        compute='_get_t_is_delivery_invoice_policy',
        string=_('Is order delivery invoice policy?'),
        readonly=True,
        store=True
    )

    all_qty_delivered = fields.Boolean(
        compute="_compute_all_qty_delivered",
        string="All quantities delivered",
        store=True,
    )

    payment_term_name = fields.Char(related='payment_term_id.name')


    @api.depends("order_line.qty_delivered", "order_line.product_uom_qty")
    def _compute_all_qty_delivered(self):
        precision = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )
        for order in self:
            order.all_qty_delivered = all(
                line.product_id.type not in ("product", "consu")
                or float_compare(
                    line.qty_delivered, line.product_uom_qty, precision_digits=precision
                )
                == 0
                for line in order.order_line
            )

    @api.depends('t_invoice_policy')
    def _get_t_is_delivery_invoice_policy(self):
        for r in self:
            r.t_is_delivery_invoice_policy = r.t_invoice_policy == 'delivery'

    @api.depends('picking_ids.state')
    def _compute_t_done_pickings(self):
        for r in self:
            r.t_done_pickings = r.picking_ids.filtered(
                lambda picking: picking.state == 'done'
            )

    @api.depends('invoice_ids.state', 'invoice_ids.amount_total')
    def _get_t_is_paid(self):
        precision = self.env['decimal.precision'].precision_get('Product Price')

        for r in self:
            if len(r.invoice_ids) == 0:
                r.t_is_paid = False
                continue

            paid_invoices = r.invoice_ids.search_read(
                [
                    ['id', 'in', r.invoice_ids.ids],
                    ['invoice_payment_state', '=', 'paid'],
                ],
                ['amount_total']
            )

            r.t_is_paid = float_compare(
                r.amount_total,
                sum(inv['amount_total'] for inv in paid_invoices),
                precision_digits=precision
            ) == 0

    @api.onchange('payment_term_id')
    def _onchange_payment_term_id(self):
        if self.payment_term_id and self.payment_term_id.t_invoice_delivered_quantities:
            self.t_invoice_policy = 'delivery'

    @api.model
    def get_deliveries(self):
        return self.env['stock.picking'].search([['origin', '=', self.name]])

    @api.model
    def cron_confirm_orders_when_invoice_paid(self):
        self.search([
            ['state', 'in', ['draft']],
            ['invoice_ids.invoice_payment_state', '=', 'paid'],
        ]).confirm_orders_when_invoice_paid()

    def confirm_orders_when_invoice_paid(self):
        for r in self:
            try:
                if not set(r.invoice_ids.mapped('invoice_payment_state')).intersection(['paid']):
                    continue
                if r.state not in ['draft']:
                    continue
                r.action_confirm()
            except Exception as e:
                subject = 'Error running cron "confirm_orders_when_invoice_paid" for {}'.format(r)
                header_text = ''
                body = 'Error running cron "confirm_orders_when_invoice_paid" for {so}: \n {error_desc}'.format(so=r, error_desc=str(e))

                msg = self.env['mail.message'].sudo().new(dict(body=body))
                notif_layout = self.env.ref('mail.mail_notification_light')
                notif_values = {'model_description': header_text, 'company': self.env.user.company_id}
                body_html = notif_layout.render(dict(message=msg, **notif_values), engine='ir.qweb', minimal_qcontext=True)
                body_html = self.env['mail.thread']._replace_local_links(body_html)
                email = self.env.user.work_email or self.env.user.email
                if not email:
                    raise ValidationError(_("You must configure your mail address."))
                mail_values = {
                    'email_from': formataddr((self.env.user.name, email)),
                    'email_to': formataddr((self.env.user.name, email)),
                    'subject': subject
                }
                self.env['mail.mail'].create(dict(body_html=body_html, state='outgoing', **mail_values))

    # Some overrides for Odoo base code
    # SO-44999 -- include 'draft' state too
    def _force_lines_to_invoice_policy_order(self):
        for line in self.order_line:
            if self.state in ['draft', 'sale', 'done']:
                line.qty_to_invoice = line.product_uom_qty - line.qty_invoiced
            else:
                line.qty_to_invoice = 0

    # Some overrides for Odoo base code
    # SO-44999 -- include 'draft' state too
    # Also, use line.t_invoice_policy
    @api.depends('state', 'product_uom_qty', 'qty_delivered', 'qty_to_invoice', 'qty_invoiced')
    def _compute_invoice_status(self):
        """
        Compute the invoice status of a SO line. Possible statuses:
        - no: if the SO is not in status 'sale' or 'done', we consider that there is nothing to
          invoice. This is also hte default value if the conditions of no other status is met.
        - to invoice: we refer to the quantity to invoice of the line. Refer to method
          `_get_to_invoice_qty()` for more information on how this quantity is calculated.
        - upselling: this is possible only for a product invoiced on ordered quantities for which
          we delivered more than expected. The could arise if, for example, a project took more
          time than expected but we decided not to invoice the extra cost to the client. This
          occurs onyl in state 'sale', so that when a SO is set to done, the upselling opportunity
          is removed from the list.
        - invoiced: the quantity invoiced is larger or equal to the quantity ordered.
        """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for line in self:
            if line.state not in ('draft', 'sale', 'done'):
                line.invoice_status = 'no'
            elif not float_is_zero(line.qty_to_invoice, precision_digits=precision):
                line.invoice_status = 'to invoice'
            elif line.state in ('draft', 'sale') and line.t_invoice_policy == 'order' and\
                    float_compare(line.qty_delivered, line.product_uom_qty, precision_digits=precision) == 1:
                line.invoice_status = 'upselling'
            elif float_compare(line.qty_invoiced, line.product_uom_qty, precision_digits=precision) >= 0:
                line.invoice_status = 'invoiced'
            else:
                line.invoice_status = 'no'

    def action_confirm(self):
        ret = super(SaleOrder, self).action_confirm()

        # SO-44999 Create & validate invoice after non-delivery invoice_policy
        # order is confirmed
        if self.t_invoice_policy != 'delivery':
            self._create_invoice()

        return ret

    def _create_invoice(self):
        if self.invoice_status == 'invoiced':
            return

        invoice_ids = set(self.invoice_ids.ids)

        wiz_id = self.env['sale.advance.payment.inv'].with_context(
            active_model='sale.order',
            active_id=self.id
        ).create({
            'advance_payment_method': 'delivered',
        })
        wiz_id.with_context(active_ids=self.ids).create_invoices()

        new_invoice_ids = self.invoice_ids.filtered(
            lambda inv: inv.id not in invoice_ids
        )
        new_invoice_ids.action_post()

    def _send_invoice(self):
        for new_invoice in self.invoice_ids.filtered(lambda i: not i.invoice_sent and i.state != 'cancel' and i.type == 'out_invoice'):
            view_data = new_invoice.action_invoice_sent()
            ctx = dict(active_ids=new_invoice.ids, **view_data['context'])
            send_id = self.env[view_data['res_model']].with_context(**ctx).create({
                'composition_mode': 'comment',
                'invoice_ids': [(6, None, new_invoice.ids)],
                'is_email': True,
                'partner_ids': [(6, None, self.partner_id.ids)],
                'template_id': self.env.ref('tameson_mail.email_template_edi_invoice_tameson').id,
            })
            # This is to trigger template_id change, to fill in template's
            # subject and body
            send_id.onchange_template_id()
            print_data = send_id.with_context(**ctx).send_and_print_action()
            if 'report_file' not in print_data:
                return
            report = self.env['ir.actions.report'].sudo().search([
                ['report_file', '=', print_data['report_file']],
                ['report_name', '=', print_data['report_name']],
                ['report_type', '=', print_data['report_type']],
            ])
            report.render_qweb_pdf(new_invoice.ids)

    @api.model
    def cron_check_sale_order_has_validated_invoice_for_done_pickings(self):
        self.check_sale_order_has_validated_invoice_for_done_pickings()

    # validators
    def check_sale_order_has_validated_invoice_for_done_pickings(self):
        # The SQL is for performance reasons
        # We are looking for sale.order (id, origin) pairs such that:
        # 1. they have 'done' pickings
        # 2. they have no 'open' nor 'paid' invoices

        self._cr.execute("""
        WITH ok_invoices AS (
          SELECT invoice_origin AS origin FROM account_move
            WHERE invoice_payment_state IN ('open', 'paid')
        ), joined_origins AS (
          SELECT
              so.id AS so_id,
              sp.origin AS sp_origin,
              ok_invoices.origin AS oi_origin
            FROM sale_order AS so
            JOIN stock_picking AS sp
              ON so.name = sp.origin
            LEFT JOIN ok_invoices
              ON sp.origin = ok_invoices.origin
            WHERE sp.state = 'done'
              AND so.state != 'cancel'
        )
        SELECT DISTINCT so_id, sp_origin FROM joined_origins
          WHERE oi_origin IS NULL
        """)

        wrong_sale_orders = [(r[0], r[1]) for r in self._cr.fetchall()]

        if wrong_sale_orders:
            sof = '<br/>'.join('{} ({})'.format(so[1], so[0]) for so in wrong_sale_orders)

            subject = 'Sale orders with "done" pickings found which have unvalidated invoices.'
            header_text = ''
            body = """
            The following sale orders have pickings in 'done' state but have no validated invoices: <br/>
            {}
            """.format(sof)

            msg = self.env['mail.message'].sudo().new(dict(body=body))
            notif_layout = self.env.ref('mail.mail_notification_light')
            notif_values = {'model_description': header_text, 'company': self.env.user.company_id}
            body_html = notif_layout.render(dict(message=msg, **notif_values), engine='ir.qweb', minimal_qcontext=True)
            body_html = self.env['mail.thread']._replace_local_links(body_html)
            email = self.env.user.work_email or self.env.user.email
            if not email:
                raise ValidationError(_("You must configure your mail address."))
            mail_values = {
                'email_from': formataddr((self.env.user.name, email)),
                'email_to': formataddr((self.env.user.name, email)),
                'subject': subject
            }
            self.env['mail.mail'].create(dict(body_html=body_html, state='outgoing', **mail_values))

            if self.env.context.get('raise_errors'):
                raise Exception(wrong_sale_orders)

    ##Add delivery method only if delivery_id is not set for new SO
    @api.model_create_multi
    def create(self, vals):
        res = super(SaleOrder, self).create(vals)
        for order in res:
            if not order.carrier_id and order.order_line and order.partner_id.country_id and order.partner_id.country_id.select_shipment_id:
                order._add_default_shipping()
        return res
    #Function for adding defaulr delivery method from partner country configuration.
    def _add_default_shipping(self):
        choose_carrier = self.env['choose.delivery.carrier'].with_context({
                    'default_order_id': self.id,
                    'default_carrier_id': self.partner_id.country_id.select_shipment_id.id,
                    }).create({})
        choose_carrier._onchange_carrier_id()
        if choose_carrier.carrier_id.delivery_type not in ('fixed', 'base_on_rule'):
            choose_carrier.update_price()
        choose_carrier.button_confirm()
        return True

    #update default country delivery method if partner is changed.
    def write(self, values):
        result = super(SaleOrder, self).write(values)
        if 'partner_id' in values:
            for order in self:
                order.order_line.filtered(lambda l: l.is_delivery).unlink()
                if order.order_line and order.partner_id.country_id and order.partner_id.country_id.select_shipment_id:
                    order._add_default_shipping()
        return result
    

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    t_invoice_policy = fields.Selection(
        [
            ('order', 'Ordered quantities'),
            ('delivery', 'Delivered quantities'),
            ('cost', 'Invoice based on time and material')
        ],
        string=_('Invoicing Policy (overrides product invoice policies)'),
        compute='_get_t_invoice_policy'
    )

    @api.depends('order_id.t_invoice_policy', 'product_id.invoice_policy', 'product_id.type')
    def _get_t_invoice_policy(self):
        for line in self:
            if line.product_id.type == 'product':
                line.t_invoice_policy = line.order_id.t_invoice_policy or line.product_id.invoice_policy
            else:
                line.t_invoice_policy = line.product_id.invoice_policy

    # Some overrides for Odoo base code
    # SO-44999 -- include 'draft' state too
    @api.depends('qty_invoiced', 'qty_delivered', 'product_uom_qty', 'order_id.state', 't_invoice_policy')
    def _get_to_invoice_qty(self):
        """
        Compute the quantity to invoice. If the invoice policy is order, the quantity to invoice is
        calculated from the ordered quantity. Otherwise, the quantity delivered is used.
        """
        for line in self:
            if line.order_id.state in ['draft', 'sale', 'done']:
                if line.t_invoice_policy == 'order':
                    line.qty_to_invoice = line.product_uom_qty - line.qty_invoiced
                else:
                    line.qty_to_invoice = line.qty_delivered - line.qty_invoiced
            else:
                line.qty_to_invoice = 0



class MailComposer(models.TransientModel):
    _inherit = 'mail.compose.message'

    def onchange_template_id(self, template_id, composition_mode, model, res_id):
        InvoiceReport = self.env.ref('account.account_invoices')
        ProformaReport = self.env.ref('sale.action_report_pro_forma_invoice')
        Attachment = self.env['ir.attachment']

        vals = super(MailComposer, self).onchange_template_id(template_id, composition_mode, model, res_id)
        if template_id == self.env.ref('tameson_sale.tameson_sale_order_confirmation_prepay').id and composition_mode != 'mass_mail':
            invoices = self.env[model].browse(res_id).invoice_ids
            if invoices :
                result, format = InvoiceReport.render_qweb_pdf(invoices.ids)
                report_name = (', '.join(invoices.mapped('name')) or 'Invoice').replace('/','_') + '.pdf'
            else:
                result, format = ProformaReport.render_qweb_pdf([res_id])
                report_name = "Proforma.pdf"
            result = base64.b64encode(result)
            attachment = Attachment.create({
                'name': report_name,
                'datas': result,
                'res_model': 'mail.compose.message',
                'res_id': 0,
                'type': 'binary'
            })
            vals['value']['attachment_ids'] += [(4, attachment.id, 0)]
        return vals