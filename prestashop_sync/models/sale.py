
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare

CURRENCIES = {
    '1': 'EUR',
    '3': 'GBP',
    '4': 'USD'
}

DOMAIN = {
    '1': 'magneetventielshop.nl',
    '2': 'tameson.co.uk',
    '3': 'tameson.com'
}

class SaleOrderPresta(models.Model):
    _inherit = 'sale.order'
    
    prestashop_id = fields.Char(string='Prestashop ID', index=True, copy=False)
    prestashop_module = fields.Char(string='Prestashop Module', index=True, copy=False)
    prestashop_date_upd = fields.Datetime(string='Prestashop update time', index=True, copy=False)
    prestashop_config_id = fields.Many2one(string='Prestashop', comodel_name='prestashop.config', ondelete='set null',index=True, copy=False)
    prestashop_state = fields.Char(string='Prestashop current state', index=True, copy=False)

    shipped_status_prestashop = fields.Boolean(string='Prestashop shipped', default=False, readonly=True, copy=False)
    force_all_qty_delivered = fields.Boolean(string='Force prestashop shipped', default=False, copy=False)
    
    _sql_constraints = [
        (
            'prestashop_id unique',
            'unique (prestashop_id)',
            _('Prestashop ID must be unique.')
        )
    ]
    
    def create_from_prestashop(self, task_uuid, order, **kwargs):
        partner, delivery, invoice = self.env['res.partner'].match_or_create_prestashop(order)
        order_data = order['order']
        prestashop_id = order_data['id']
        prestashop_module = order_data['module']
        prestashop_date_upd = order_data['date_upd']
        prestashop_config_id = order['config_id']
        config_id = self.env['prestashop.config'].browse(prestashop_config_id)
        currency_id = self.env['res.currency'].search([('name','=',CURRENCIES[order_data['id_currency']])], limit=1)
        pricelist_id = self.env['product.pricelist'].search([('currency_id','=',currency_id.id)],limit=1)
        if not pricelist_id:
            raise UserError('%s currency pricelist not found.' % CURRENCIES[order_data['id_currency']])
        lines = []
        for line in order_data['order_rows']:
            product_id = self.env['product.product'].search([('default_code','=ilike',line['product_reference'])],limit=1)
            if not product_id:
                raise UserError('Product for reference %s not found.' % line['product_reference'])
                # product_id = self.env['product.product'].create({'default_code': line['product_reference'], 'name': line['product_name']})
            lines.append((0, 0, {
                'product_id': product_id.id, 
                'name': product_id.name, 
                'product_uom_qty': float(line['product_quantity']),
                'price_unit': float(line['unit_price_tax_excl']),
                }
            ))
        order_vals = {
            'partner_id': partner.id,
            'payment_term_id': partner.property_payment_term_id.id,
            'partner_shipping_id': delivery.id,
            'partner_invoice_id': invoice.id,
            'pricelist_id': pricelist_id.id,
            'prestashop_id': prestashop_id,
            'prestashop_module': prestashop_module,
            'prestashop_date_upd': prestashop_date_upd,
            'prestashop_config_id': prestashop_config_id,
            'order_line': lines,
            'presta_ups_access_point_country': order_data.get('ups_country_iso', {}).get('value', False),
            'presta_ups_access_point_id': order_data.get('ups_id_access_point', {}).get('value', False),
            'prestashop_state': order_data['current_state'],
            'client_order_ref': order_data.get('user_reference', {}).get('value', False),
            'origin': "%s - %s - %s" % (DOMAIN.get(order_data.get('id_shop', ''), ''), prestashop_id, order_data.get('reference', ''),),
            'source_id': config_id.source_id.id
        }
        carrier = order_data.get('id_carrier', '0')
        carrier_id = bool(carrier) and self.env['delivery.carrier'].search([('prestashop_carrier_ids','=',carrier)], limit=1)
        if carrier_id:
            lines.append((0, 0, {
                    'product_id': carrier_id.product_id.id,
                    'product_uom_qty': 1, 
                    'name': carrier_id.product_id.name, 
                    'price_unit': order_data.get('total_shipping_tax_excl', 0),
                    'is_delivery': True
                    }
                )
            )
            order_vals.update({
                'carrier_id': carrier_id.id,
                'order_line': lines
            })
        else:
            if carrier:
                raise UserError('Carrier name doesn\'t match with any shipping method in Odoo')

        total_discounts_tax_excl = float(order_data.get('total_discounts_tax_excl', 0))
        if total_discounts_tax_excl > 0:
            lines.append((0, 0, {
                    'product_id': config_id.discount_product_id.id,
                    'product_uom_qty': 1, 
                    'name': 'Webshop discount', 
                    'price_unit': -total_discounts_tax_excl,
                    }
                )
            )

        Order = self.create(order_vals)
        Order.onchange_partner_shipping_id()
        Order.recompute()
        Order._compute_tax_id()
        Order.flush()
        invoice_email = order_data.get('user_invoice_email', {}).get('value', False)
        if invoice_email:
            if not Order.partner_invoice_id.email:
                Order.partner_invoice_id.email = invoice_email
        return Order.name
    
    def update_from_prestashop(self, task_uuid, so_id, order, **kwargs):
        prestashop_module = order['module']
        prestashop_date_upd = order['date_upd']
        so_id = self.browse(so_id)
        so_id.write({
            'prestashop_module': prestashop_module,
            'prestashop_date_upd': prestashop_date_upd,
            'prestashop_state': order['current_state'],
        })
        return True

    def prestashop_order_process(self, task_uuid, so_id, data, **kwargs):
        self = self.browse(so_id)
        presta_total = float(data['total_paid_tax_incl'])
        price_difference = abs(presta_total - self.amount_total)
        ## float_compare 1 means price difference greater allowed value
        if float_compare(price_difference, self.prestashop_config_id.price_def_allowed, precision_digits=2) == 1:
            raise UserError('Total amount mismatch odoo: %.2f presta: %.2f' % (self.amount_total, presta_total))
        module = data['module']
        if module == 'invoicepayment':
            if self.state == 'sale':
                return True
            self.t_invoice_policy = 'delivery'
            self.action_confirm()
        elif module == 'ps_wirepayment':
            if self.invoice_ids:
                return True
            prepayment = self.env['account.payment.term'].search([('name','=','Prepayment')], limit=1)
            self.write({
                'payment_term_id': prepayment.id,
                't_invoice_policy': 'order'
            })
            wizard = self.env['sale.advance.payment.inv'].with_context({'active_model': self._name, 'active_id': self.id, 'active_ids': self.ids}).\
                create({'advance_payment_method': 'delivered'})
            wizard.create_invoices()
            self.invoice_ids.action_post()
        else:
            if self.state == 'sale':
                return True
            self.action_confirm()
            journal_id = self.env['account.journal']
            if module and module == 'adyencw_paypal':
                journal_id = journal_id.search([('name','ilike','paypal')], limit=1)
            elif module and module.startswith('adyencw'):
                journal_id = journal_id.search([('name','ilike','adyen')], limit=1)
            if not journal_id:
                raise UserError('Journal not found for module %s order %s prestashop_id %s' % (module, self.name, self.prestashop_id))
            payment_method_id = journal_id.inbound_payment_method_ids.ids[0]
            payment_env = self.env['account.payment'].with_context(active_ids=self.invoice_ids.ids, active_model='account.move', active_id=self.invoice_ids.id)
            payment = payment_env.create({
                'journal_id': journal_id.id,
                'payment_method_id': payment_method_id,
            })
            payment._onchange_journal()
            payment.post()
            self.invoice_ids.post()
        return True