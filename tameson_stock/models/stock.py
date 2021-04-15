import codecs
import six
import tempfile
import base64
from datetime import datetime
from dateutil.relativedelta import relativedelta
from wand.image import Image

from odoo import api, fields, models, _
from odoo.tools.pdf import merge_pdf
from odoo.exceptions import UserError, ValidationError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    t_delivery_allowed = fields.Boolean(
        compute='_t_delivery_allowed_get',
        string=_('Delivery allowed'),
        store=True,
        readonly=False
    )
    t_invoice_ids_to_report = fields.Many2many(
        'account.move',
        compute='_compute_t_invoice_ids_to_report',
        string=_('Invoices to report')
    )
    t_partner_outside_eu = fields.Boolean(
        string=_('Out of EU'),
        compute='_get_t_partner_outside_eu',
        search='_search_t_partner_outside_eu',
        readonly=True
    )
    t_payment_status = fields.Boolean(
        compute='_t_payment_status_get',
        string=_('Fully paid'),
        store=True
    )

    @api.depends('sale_id', 'state', 'sale_id.t_is_delivery_invoice_policy', 'sale_id.t_is_paid')
    def _t_delivery_allowed_get(self):
        for r in self:
            order = r.sale_id

            r.t_delivery_allowed = bool(
                order and (
                    order.t_is_delivery_invoice_policy or r.t_payment_status
                )
            )

    @api.depends('origin')
    def _compute_t_invoice_ids_to_report(self):
        invoice_ids = self.env['account.move'].search([
            ['invoice_origin', 'in', self.mapped('origin')],
            ['state', 'not in', ['draft', 'cancel']]
        ])

        for r in self:
            r.t_invoice_ids_to_report = invoice_ids.filtered(lambda i: i.invoice_origin == r.origin)

    @api.depends('partner_id')
    def _get_t_partner_outside_eu(self):
        eu_group = self.env['ir.model.data'].get_object('base', 'europe')
        eu_country_ids = eu_group.country_ids.ids
        for sp in self:
            sp.t_partner_outside_eu = sp.partner_id.country_id.id not in eu_country_ids

    def _search_t_partner_outside_eu(self, operator, value):
        eu_group = self.env['ir.model.data'].get_object('base', 'europe')
        eu_country_ids = eu_group.country_ids.ids
        op = 'in'
        if operator == '=':
            if value:
                op = 'not in'
            else:
                op = 'in'
        elif operator == '!=':
            if value:
                op = 'in'
            else:
                op = 'not in'
        else:
            raise Exception('Unhandled operator {}'.format(operator))

        return [
            ('partner_id.country_id.id', op, eu_country_ids)
        ]

    @api.depends('sale_id', 'sale_id.t_is_paid')
    def _t_payment_status_get(self):
        for r in self:
            order = r.sale_id
            r.t_payment_status = order and order.t_is_paid

    def action_done(self):
        rets = True
        # SO-44999 Create invoice for 'delivery' invoice policy
        for r in self:
            try:
                ret = super(StockPicking, r).action_done()
                rets = rets and ret
            except UserError as e:
                msg = "%s: %s" % (r.name, e.name)
                raise UserError(msg)
            except ValidationError as e:
                msg = "%s: %s" % (r.name, e.name)
                raise ValidationError(msg)
            if r.sale_id:
                if r.sale_id.t_invoice_policy == 'delivery' or r.sale_id.all_qty_delivered:
                    r.sale_id._create_invoice()
                    r.sale_id._send_invoice()
            # SO-45007 don't do auto invoices for purchase orders
            # elif r.purchase_id:
            #     if r.purchase_id.t_purchase_method == 'receive':
            #         r.purchase_id._create_invoice()

        return rets

    def fill_done_qtys(self):
        for r in self:
            for ml in r.move_ids_without_package:
                ml.quantity_done = ml.product_uom_qty

    def get_ups_attachments(self):
        """Find attachments that match the UPS label name."""
        return self.env['ir.attachment'].search([
            ['name', '=like', 'LabelUPS%pdf'],
            ['type', '=', 'binary'],
            ['res_model', '=', 'stock.picking'],
            ['res_id', 'in', self.ids],
        ])

    def get_merged_ups_labels(self):
        return merge_pdf([
            codecs.decode(att.datas, 'base64')
            for att in self.get_ups_attachments()
        ])

    def action_mail_send(self):
        ''' Opens a wizard to compose an email, with relevant mail template loaded by default '''
        self.ensure_one()
        lang = self.partner_id.lang
        template = self.env['mail.template'].search([('model','=',self._name)], limit=1)
        if template.lang:
            lang = template._render_template(template.lang, self._name, self.ids[0])
        ctx = {
            'default_model': self._name,
            'default_res_id': self.ids[0],
            'default_use_template': bool(template),
            'default_template_id': template.id,
            'default_composition_mode': 'comment',
            'custom_layout': "mail.mail_notification_light",
            'force_email': True,
            'model_description': 'Order',
        }
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': ctx,
        }

    def get_invoice_date(self):
        return self.sale_id.invoice_ids.filtered(lambda i: i.invoice_payment_state != 'paid')[:1].invoice_date

    def generate_non_ups_labels(self):
        for r in self:
            if r.carrier_id.ups_username:
                continue

            # don't regenerate a label if it exists already
            if r.get_non_ups_labels():
                continue

            pdf, _ = self.env.ref('tameson_stock.t_delivery_addresses').render_qweb_pdf([r.id])
            attachments = [('DeliveryAddresses.pdf', pdf)]
            r.message_post(body='Delivery addresses', attachments=attachments)

    def get_non_ups_labels(self):
        """Find attachments that match the UPS label name."""
        query = [
            ['name', '=like', 'DeliveryAddresses%pdf'],
            ['type', '=', 'binary'],
            ['res_model', '=', 'stock.picking'],
            ['res_id', 'in', self.ids],
        ]

        return self.env['ir.attachment'].search(query)

    def get_merged_labels(self):
        ups_attachments = self.get_ups_attachments()
        non_ups = self.get_non_ups_labels()
        att_dict = {att.res_id: att for att in ups_attachments}
        att_dict.update({att.res_id: att for att in non_ups})

        return merge_pdf([
            codecs.decode(att_dict[sp_id].datas, 'base64')
            for sp_id in self.ids
        ])


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    def get_ups_image_attachments(self, format='png'):
        yield from self.picking_ids.get_ups_image_attachments(format=format)

    def print_batch_stock_picking_invoices(self):
        return self.env.ref('tameson_stock.batch_stock_picking_invoices').report_action(self)


class MailComposer(models.TransientModel):
    _inherit = 'mail.compose.message'

    def onchange_template_id(self, template_id, composition_mode, model, res_id):
        SaleReport = self.env.ref('sale.action_report_saleorder')
        InvoiceReport = self.env.ref('account.account_invoices')
        PurchaseReport = self.env.ref('purchase.action_report_purchase_order')
        Attachment = self.env['ir.attachment']

        Delay = self.env.ref('tameson_stock.tameson_picking_order_delay')
        NoPay = self.env.ref('tameson_stock.tameson_picking_no_payment_received')
        NoPayCancel = self.env.ref('tameson_stock.tameson_picking_no_payment_cancel')
        PurchaseDateUpdate = self.env.ref('tameson_stock.tameson_po_delivery_date_update')

        vals = super(MailComposer, self).onchange_template_id(template_id, composition_mode, model, res_id)
        result = False
        if template_id == Delay.id and composition_mode != 'mass_mail':
            order = self.env[model].browse(res_id).sale_id
            if order:
                result, format = SaleReport.render_qweb_pdf([order.id])
                report_name = order.name + '.pdf'

        if template_id in (NoPay.id, NoPayCancel.id) and composition_mode != 'mass_mail':
            open_invoice = self.env[model].browse(res_id).sale_id.invoice_ids.filtered(lambda i: i.invoice_payment_state != 'paid')[:1]
            if open_invoice:
                result, format = InvoiceReport.render_qweb_pdf([open_invoice.id])
                report_name = open_invoice.name.replace('/','_') + '.pdf'

        if template_id == PurchaseDateUpdate.id and composition_mode != 'mass_mail':
            purchase = self.env[model].browse(res_id).purchase_id
            if purchase:
                result, format = PurchaseReport.render_qweb_pdf([purchase.id])
                report_name = purchase.name + '.pdf'

        if result:
            result = base64.b64encode(result)
            attachment = Attachment.create({
                'name': report_name,
                'datas': result,
                'res_model': 'mail.compose.message',
                'res_id': 0,
                'type': 'binary'
            })
            vals['value']['attachment_ids'] = [(6, 0, attachment.ids)]

        return vals
