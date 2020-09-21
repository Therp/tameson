import codecs
import six
import tempfile
from datetime import datetime
from dateutil.relativedelta import relativedelta
from wand.image import Image

from odoo import api, fields, models, _
from odoo.tools.pdf import merge_pdf


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
        ret = super(StockPicking, self).action_done()

        # SO-44999 Create invoice for 'delivery' invoice policy
        for r in self:
            if r.sale_id:
                if r.sale_id.t_invoice_policy == 'delivery' or r.sale_id.all_qty_delivered:
                    r.sale_id._create_invoice()
                    r.sale_id._send_invoice()
            # SO-45007 don't do auto invoices for purchase orders
            # elif r.purchase_id:
            #     if r.purchase_id.t_purchase_method == 'receive':
            #         r.purchase_id._create_invoice()

        return ret

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


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    def get_ups_image_attachments(self, format='png'):
        yield from self.picking_ids.get_ups_image_attachments(format=format)
