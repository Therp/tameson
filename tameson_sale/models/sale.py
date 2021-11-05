import base64, re

from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError
from odoo.tools import formataddr, float_compare, float_is_zero

class SaleOrder(models.Model):
    _name= 'sale.order'
    _inherit = ['sale.order', 'set.help.mixin']
    
    bypass_credit_limit = fields.Boolean(tracking=True)

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

    payment_term_name = fields.Char(
        related='payment_term_id.name',
        string='Payment Term name'
    )
    channel_process_payment = fields.Boolean()

    any_non_returnable = fields.Boolean(compute='_check_any_non_returnable')
    any_use_up = fields.Boolean(compute='_check_any_non_returnable')
    non_returnable_skus = fields.Char(compute='_check_any_non_returnable')
    uu_skus = fields.Char(compute='_check_any_non_returnable')
    uu_replacement_skus = fields.Char(compute='_check_any_non_returnable')
    
    @api.depends('order_line.product_id.non_returnable', 'order_line.product_id.t_use_up')
    def _check_any_non_returnable(self):
        for record in self:
            nr_products = self.order_line.mapped('product_id').filtered(lambda p: p.non_returnable)
            record.any_non_returnable = bool(nr_products)
            record.non_returnable_skus = ','.join(nr_products.mapped('default_code') or [])
            
            uu_products = self.order_line.mapped('product_id').filtered(lambda p: p.t_use_up)
            uur_products = self.order_line.mapped('product_id').filtered(lambda p: p.t_use_up_replacement_sku)
            record.any_use_up = bool(uu_products)
            record.uu_skus = ','.join(uu_products.mapped('default_code' ))
            record.uu_replacement_skus = ','.join(uur_products.mapped(lambda p: ' %s will be replaced by %s' % (p.default_code, p.t_use_up_replacement_sku)))

    @api.onchange('order_line', 'any_use_up')
    def _onchange_any_use_up(self):
        note = re.sub('\nWarning: \S+ is being discontinued.', "", self.note)
        note = re.sub(' \S+ will be replaced by \S+,*', "", note)
        if self.any_use_up:
            warning_text = '\nWarning: %s is being discontinued.%s' % (self.uu_skus, self.uu_replacement_skus)
            note = note + warning_text
        self.note = note

    @api.onchange('order_line', 'any_non_returnable')
    def _onchange_non_returnable(self):
        pattern = '\nWarning: We kindly inform you that this item \S+ cannot be returned. This is manufactured on demand for you.'
        note = re.sub(pattern, "", self.note)
        if self.any_non_returnable:
            warning_text = '\nWarning: We kindly inform you that this item %s cannot be returned. This is manufactured on demand for you.' % self.non_returnable_skus
            note = note + warning_text
        self.note = note

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
    
    def action_create_product(self):
        action = self.env.ref('tameson_sale.action_product_creation_wizard_act_window')
        return action.read()[0]

    @api.onchange('t_invoice_policy')
    def _onchange_t_invoice_policy(self):
        if self.t_invoice_policy == 'delivery':
            self.require_payment = False
            self.require_signature = True
        else:
            self.require_payment = True
            self.require_signature = False

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
        parent_partner = self.env['res.partner'].search([('id', 'parent_of', self.partner_id.id), ('parent_id','=',False)], limit=1)
        if not self.bypass_credit_limit and self.t_invoice_policy == 'delivery':
            credit_limit = parent_partner.credit_limit
            open_orders = self.search([('partner_id', 'child_of', parent_partner.id), ('state','=','sale'), ('state','=','sale')]).\
                filtered(lambda so: 'posted' not in so.invoice_ids.mapped('state'))
            open_invoices = parent_partner.unreconciled_aml_ids.mapped('move_id')
            credit = parent_partner.credit
            open_orders_total = 0
            for order in open_orders + self:
                open_orders_total += order.currency_id._convert(order.amount_total, self.env.user.company_id.currency_id,
                                    self.env.user.company_id, fields.Date.today())
            difference = (credit + open_orders_total) - credit_limit
            if credit_limit and  difference > 0:
                invoices = ', '.join(open_invoices.mapped('name'))
                orders = ', '.join(open_orders.mapped('name'))
                msg = "Credit limit: %.2f, Total due: %.2f, Total open order amount: %.2f, Difference: %.2f\nOpen invoices: %s\nOpen orders: %s" %\
                    (credit_limit, credit, open_orders_total, difference, invoices, orders)
                raise ValidationError(msg)
        ret = super(SaleOrder, self).action_confirm()

        # SO-44999 Create & validate invoice after non-delivery invoice_policy
        # order is confirmed
        if self.t_invoice_policy != 'delivery' and not self.transaction_ids:
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


    def _get_sale_order_has_issues(self):
        self._cr.execute("""
select distinct(so.id) so_id,
    so.name so_name
from sale_order so
    left join sale_order_line sol on sol.order_id = so.id
    left join sale_order_line_invoice_rel sli_rel on sol.id = sli_rel.order_line_id
    left join account_move_line aml on aml.id = sli_rel.invoice_line_id
where so.state in ('sale', 'done')
    AND aml.parent_state = 'draft'
union
select sot.so_id,
    sot.so_name
from (
        select so.id as so_id,
            so.name as so_name,
            sum(sol.qty_delivered) as sum_qty_delivered,
            sum(
                case
                    when aml.id is null then 0
                    else 1
                end
            ) as aml_count
        from sale_order so
            left join sale_order_line sol on sol.order_id = so.id
            left join sale_order_line_invoice_rel sli_rel on sol.id = sli_rel.order_line_id
            left join account_move_line aml on aml.id = sli_rel.invoice_line_id
        where so.state in ('sale', 'done')
        group by so.id
    ) as sot
where sot.aml_count = 0
    and sot.sum_qty_delivered > 0 """)

        wrong_sale_orders = [(r[0], r[1]) for r in self._cr.fetchall()]
        vals = []
        if wrong_sale_orders:
            vals.append({'name': 'Sale orders that have a confirmed delivery, but no confirmed invoice', 'orders': wrong_sale_orders})
        return vals

    def check_sale_order_has_issues(self):
        sections = self._get_sale_order_has_issues()
        partners = self.env.ref('tameson_sale.notification_faulty_sale_orders').users.mapped('partner_id')
        if sections and partners:
            template = self.env.ref('tameson_sale.tameson_sale_order_issue_notify')
            template.with_context(sections=sections).send_mail(self.env.user.partner_id.id, force_send=True, email_values={'recipient_ids': [(6, 0, partners.ids)]})


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
    
    def process_channel_payment(self):
        return True


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

    @api.onchange('product_id', 'product_uom_qty')
    def _onchange_product_id_set_customer_lead(self):
        self.customer_lead = self.product_id.sale_delay
        if self.product_id and self.product_id.virtual_available < self.product_uom_qty:
            self.customer_lead = self.product_id.sale_delay + self.product_id._select_seller(quantity=self.product_uom_qty).delay

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
