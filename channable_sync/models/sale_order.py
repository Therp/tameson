import requests
import datetime
import pytz
import json
from dateutil import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons.celery.models.celery_task import STATE_PENDING as CELERY_STATE_PENDING

import logging
_logger = logging.getLogger(__name__)

def _log_logging(env, message, function_name, path):
    env['ir.logging'].sudo().create({
        'name': 'Prestashop',
        'type': 'server',
        'level': 'WARN',
        'dbname': env.cr.dbname,
        'message': message,
        'func': function_name,
        'path': path,
        'line': '0',
    })

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    channable_order_id = fields.Char(string="Channable Order ID", copy=False)
    channable_extra_info = fields.Text(string="Extra Info (Channable)", copy=False)
    channable_order_status = fields.Char(string="Channable Order Status", copy=False)
    channable_to_update_cancel = fields.Boolean(string="Needs To Be Cancelled in Channable", default=False, copy=False)
    channable_to_update_shipped = fields.Boolean(string="Needs To Be Updated in Channable", default=False, copy=False)
    channable_refused_cancellation = fields.Boolean(string="Refused Cancellation in Channable", default=False, copy=False)
    channable_payment_method = fields.Char(string="Channable Payment", copy=False)

    @api.model
    def cron_sync_orders_with_channable(self):
        CeleryTask = self.env['celery.task']
        domain = [
            ('model', '=', self._name),
            ('method', '=', 'sync_orders_with_channable'),
            ('state', '=', CELERY_STATE_PENDING)
        ]
        if CeleryTask.search_count(domain) == 0:
            celery = {
                'countdown': 1,
                'retry': True,
                'max_retries': 3,
                'interval_start': 5,
                'queue': 'high.priority',
            }
            celery_task_vals = {'ref': 'Sync Orders From Channable'}
            CeleryTask.call_task(self._name, 'sync_orders_with_channable', celery=celery, celery_task_vals=celery_task_vals)
        return True

    @api.model
    def sync_orders_with_channable(self, task_uuid, **kwargs):
        CeleryTask = self.env['celery.task']
        celery = {
            'countdown': 1,
            'retry': True,
            'max_retries': 2,
            'interval_start': 1,
        }
        offset, imported_orders_count = 0, 0
        limit_size = self.env['ir.config_parameter'].sudo().get_param(
            'channable_sync.limit_orders_request_size', default=20)
        try:
            limit_size = int(limit_size)
        except Exception as e:
            _logger.warning('Error in converting the limit orders request size config parameter: %s' % str(e))
            limit_size = 20
        orders_last_n_days_sync = self.env['ir.config_parameter'].sudo().get_param(
            'channable_sync.orders_last_n_days_sync', default=0)
        try:
            orders_last_n_days_sync = int(orders_last_n_days_sync)
        except Exception as e:
            _logger.warning('Error in converting the number of days sync from the Channable order API: %s' % str(e))
            orders_last_n_days_sync = 0
        payload = {
            'offset': offset,
            'limit': limit_size,
        }
        if orders_last_n_days_sync:
            start_date = fields.Date.to_string((datetime.date.today() - relativedelta.relativedelta(days=orders_last_n_days_sync)))
            end_date = fields.Date.to_string((datetime.date.today() + relativedelta.relativedelta(days=1)))
            payload.update({
                'start_date': start_date,
                'end_date': end_date,
            })
        if not all([self.company_id.channable_orders_shipped, self.company_id.channable_orders_not_shipped,
                    self.company_id.channable_orders_cancelled, self.company_id.channable_orders_waiting]):
            # fetch only orders with the selected state
            states_to_fetch = []
            if self.company_id.channable_orders_not_shipped:
                states_to_fetch.append('not_shipped')
            if self.company_id.channable_orders_shipped:
                states_to_fetch.append('shipped')
            if self.company_id.channable_orders_cancelled:
                states_to_fetch.append('cancelled')
            if self.company_id.channable_orders_waiting:
                states_to_fetch.append('waiting')
            if states_to_fetch:
                payload.update({
                    'status': states_to_fetch
                })

        response = self.env.user.company_id.channable_request(method="GET",
                                                              endpoint="/orders",
                                                              payload=payload,
                                                              timeout=600)
        all_orders = response.get('orders', [])
        while all_orders:
            for order in all_orders:
                existing_order = self.search([('channable_order_id', '=', order.get('id'))], limit=1)
                if not existing_order:
                    order_body = json.dumps(order)
                    celery_task_vals = {'ref': 'Import Channable Order: %s' % str(order.get('id'))}
                    CeleryTask.call_task(self._name, 'import_channable_order', order_body=order_body, celery=celery, celery_task_vals=celery_task_vals)
                    imported_orders_count += 1
                else:
                    # existing order, check for status change/cancellation
                    channable_status = order.get('status_shipped')
                    if channable_status == 'cancelled' and existing_order.state != 'cancel':
                        if any(pick.state == 'done' for pick in existing_order.mapped('picking_ids')):
                            existing_order.write({
                                'channable_refused_cancellation': True,
                                'channable_order_status': 'cancelled',
                            })
                            continue
                        existing_order.action_cancel()
                        existing_order.write({'channable_order_status': 'cancelled'})
                        # TODO if invoice is paid/posted -> make a refund/credit note?
            offset += limit_size
            payload.update({'offset': offset})
            response = self.env.user.company_id.channable_request(method="GET",
                                                                  endpoint="/orders",
                                                                  payload=payload,
                                                                  timeout=600)
            all_orders = response.get('orders', [])

        msg = 'Channable sync: successfully imported %s new orders.' % str(imported_orders_count)
        _logger.info(msg)
        return msg

    def import_channable_order(self, task_uuid, **kwargs):
        order_body = kwargs.get('order_body')
        try:
            order = json.loads(order_body)
        except Exception as e:
            _logger.error('Error on parsing order body/response: %s' % str(e))
            raise

        # check if it's an existing order once more
        existing_order = self.search([('channable_order_id', '=', order.get('id'))], limit=1)
        if existing_order:
            # check for status change/cancellation
            channable_status = order.get('status_shipped')
            if channable_status == 'cancelled' and existing_order.state != 'cancel':
                if any(pick.state == 'done' for pick in existing_order.mapped('picking_ids')):
                    existing_order.write({
                        'channable_refused_cancellation': True,
                        'channable_order_status': 'cancelled',
                    })
                    return 'Channable order import: order canceled in Channable, but unable to be cancelled in Odoo: %s' % str(existing_order.name)
                existing_order.action_cancel()
                existing_order.write({'channable_order_status': 'cancelled'})
                return 'Channable order import: order cancelled after being cancelled in Channable: %s' % str(existing_order.name)
            else:
                return 'Channable order import: existing order, skipping: %s' % str(existing_order.name)

        billing = order.get('data', {}).get('billing', {})
        shipping = order.get('data', {}).get('shipping', {})
        customer = order.get('data', {}).get('customer', {})
        extra_data = order.get('data', {}).get('extra', {})
        price_data = order.get('data', {}).get('price', {})
        product_lines = order.get('data', {}).get('products', [])
        currency = price_data.get('currency')

        # e-mail address is the unique identifier
        email = customer.get('email') or billing.get('email')

        partner, partner_invoice, partner_shipping = self.get_channable_customer(email, customer, billing, shipping, currency)
        if not partner:
            raise Warning(_("Customer not available in order %s." % (order.get('id'))))

        res_currency = self.env['res.currency'].search([('name', '=', currency)], limit=1)

        new_record = self.new({'partner_id': partner.id})
        new_record.onchange_partner_id()
        retval = self._convert_to_write({name: new_record[name] for name in new_record._cache})
        new_record = self.new(retval)
        new_record.onchange_partner_shipping_id()
        retval = self._convert_to_write({name: new_record[name] for name in new_record._cache})

        fiscal_position_id = partner.property_account_position_id and partner.property_account_position_id.id or False
        if not fiscal_position_id:
            fp_id = self.env['account.fiscal.position'].get_fiscal_position(partner.id)
            if fp_id:
                fiscal_position_id = fp_id
                partner.property_account_position_id = fp_id
        pricelist_id = retval.get('pricelist_id', False)
        # check the pricelist (coming from the partner) and the order currency
        if pricelist_id and res_currency:
            pricelist = self.env['product.pricelist'].browse(pricelist_id)
            if pricelist.currency_id != res_currency:
                if partner.country_id:
                    # filter by country
                    applicable_pricelist = self.env['product.pricelist'].search([('currency_id', '=', res_currency.id), ('country_group_ids.country_ids', '=', partner.country_id.id)], limit=1)
                    if not applicable_pricelist:
                        applicable_pricelist = self.env['product.pricelist'].search([('currency_id', '=', res_currency.id)], limit=1)
                else:
                    applicable_pricelist = self.env['product.pricelist'].search([('currency_id', '=', res_currency.id)], limit=1)
                if applicable_pricelist:
                    pricelist_id = applicable_pricelist.id
        payment_term = retval.get('payment_term_id', False)

        # Adjust timezone for the order date (sent in CET from Channable)
        date_order = order.get('created')
        if date_order:
            try:
                datetime_obj = datetime.datetime.strptime(date_order.split('.')[0], '%Y-%m-%dT%H:%M:%S')
            except Exception as e:
                _logger.warning('Datetime Parsing Error: %s' % (str(e), ))
                datetime_obj = False
            if datetime_obj and self.env.user.tz:
                user_timezone = pytz.timezone(self.env.user.tz)
                datetime_obj = user_timezone.localize(datetime_obj)
                datetime_obj = datetime_obj.astimezone(pytz.utc)
                datetime_obj = datetime_obj.replace(tzinfo=None)
                date_order = datetime_obj
            elif datetime_obj:
                date_order = datetime_obj
            else:
                date_order = fields.datetime.now()
        else:
            date_order = fields.datetime.now()
        values = {
            'channable_order_id': order.get('id'),
            'channable_order_status': order.get('status_shipped'),
            'partner_id': partner.id,
            'partner_invoice_id': partner_invoice.id,
            'partner_shipping_id': partner_shipping.id,
            'date_order': date_order,
            'client_order_ref': '{channel_name} {channel_id}-{platform_id}'.format(channel_name=order.get('channel_name', ''),
                                                                                   channel_id=order.get('channel_id', ''),
                                                                                   platform_id=order.get('platform_id', '')),
            'channable_extra_info': 'Comment:\n{extra_comment}\n\nMemo:\n{extra_memo}'.format(extra_comment=extra_data.get('comment', ''),
                                                                                              extra_memo=extra_data.get('memo', '')),
            'state': 'draft',
            'pricelist_id': pricelist_id,
            'fiscal_position_id': fiscal_position_id,
            'payment_term_id': payment_term,
            'channable_payment_method': price_data.get('payment_method', '')
        }
        sale_order = self.create(values)
        sale_order.flush()

        product_product = self.env['product.product']
        for line in product_lines:
            product_search_domain = ['|', ('barcode', '=ilike', line.get('ean')), ('default_code', '=ilike', line.get('id'))]
            product = product_product.search(product_search_domain, limit=1)
            if not product:
                raise Warning(_("Product %s not available in Odoo (order %s)." % ((line.get('id') or line.get('ean')), order.get('id'))))
            created_line = self.create_order_line_from_channable(sale_order=sale_order,
                                                                 product=product,
                                                                 line_data=line,
                                                                 is_delivery=False)

        if price_data.get('shipping', 0):
            product = self.env.ref('channable_sync.product_product_delivery_channable', raise_if_not_found=False)
            if product:
                line = {
                    'price': float(price_data.get('shipping', 0)),
                    'quantity': 1,
                    'title': 'Shipping',
                }
                created_line = self.create_order_line_from_channable(sale_order=sale_order,
                                                                     product=product,
                                                                     line_data=line,
                                                                     is_delivery=True)
            else:
                raise Warning(_("Shipping cost service not available in Odoo, and shipping cost exists for this order."))
        sale_order.recompute()
        sale_order.flush()

        if sale_order.company_id and sale_order.company_id.channable_auto_confirm_order:
            # automatically confirm an order
            if sale_order.company_id and sale_order.company_id.channable_auto_register_payment:
                # and also register the payment on the invoice if applicable
                sale_order.write({'channel_process_payment': True})
            sale_order.action_confirm()

        msg = 'Channable order import: successfully imported a new order: %s' % str(sale_order.name)
        _logger.info(msg)
        return msg

    def get_channable_customer(self, email, customer, billing, shipping, currency):
        partner = False
        partner_invoice = False
        partner_shipping = False

        ResPartner = self.env['res.partner']

        partner = ResPartner.search([('email', '=', email), ('type', 'not in', ['invoice', 'delivery', 'other']), ('parent_id', '=', False)], limit=1)
        if not partner:
            partner = ResPartner.search([('email', '=', email), ('parent_id', '=', False)], limit=1)
        if partner:
            is_company = False if not customer.get('company') else True
            # existing partner, update applicable info
            partner = self.update_partner_address(partner, customer, billing, is_company)

            partner_invoice = ResPartner.search([('parent_id', '=', partner.id), ('type', '=', 'invoice')], limit=1)
            partner_invoice = self.update_partner_address(partner_invoice, billing, customer, False)
            partner_shipping = ResPartner.search([('parent_id', '=', partner.id), ('type', '=', 'delivery')], limit=1)
            partner_shipping = self.update_partner_address(partner_shipping, shipping, customer, False)

            if not partner_invoice:
                partner_invoice = self.create_partner_address(data=billing, secondary_data=customer, address_type='invoice', is_company=False, parent_id=partner and partner.id or False)
            if not partner_shipping:
                partner_shipping = self.create_partner_address(data=shipping, secondary_data=customer, address_type='delivery', is_company=False, parent_id=partner and partner.id or False)
        else:
            # create a new partner
            is_company = False if not customer.get('company') else True
            partner = self.create_partner_address(data=customer, secondary_data=billing, address_type=False, is_company=is_company, parent_id=False)

            # create a new invoice address
            partner_invoice = self.create_partner_address(data=billing, secondary_data=customer, address_type='invoice', is_company=False, parent_id=partner and partner.id or False)

            # create a new delivery address
            partner_shipping = self.create_partner_address(data=shipping, secondary_data=customer, address_type='delivery', is_company=False, parent_id=partner and partner.id or False)

        if currency and not partner.property_product_pricelist:
            # set a pricelist property
            res_currency = self.env['res.currency'].search([('name', '=', currency)], limit=1)
            if res_currency:
                pricelist = self.env['product.pricelist'].search([('currency_id', '=', res_currency.id)])
                if pricelist and len(pricelist) == 1:
                    partner.write({
                        'property_product_pricelist': pricelist.id
                    })

        return partner, partner_invoice, partner_shipping

    def create_partner_address(self, data, secondary_data, address_type, is_company, parent_id):
        country_code = data.get('country_code', '') or secondary_data.get('country_code', '')
        country = self.env['res.country'].search([('code', '=', country_code)], limit=1)
        address2 = data.get('address2', '') or secondary_data.get('address2', '')
        address_supplement = data.get('address_supplement', '') or secondary_data.get('address_supplement', '')
        street2 = '{address2} {address_supplement}'.format(address2=address2, address_supplement=address_supplement)
        names = [data.get('first_name', ''), data.get('middle_name', ''), data.get('last_name', '')]
        full_name = ' '.join([n for n in names if n])
        if is_company:
            name = data.get('company', '')
            comment = full_name
        else:
            name = full_name
            comment = data.get('company', '') or secondary_data.get('company', '')
        values = {
            'name': name,
            'email': data.get('email', '') or secondary_data.get('email', ''),
            'phone': data.get('phone', '') or secondary_data.get('phone', '') or '0000000000',
            'mobile': data.get('mobile', '') or secondary_data.get('mobile', ''),
            'street': data.get('address1', '') or secondary_data.get('address1', ''),
            'street2': street2,
            'zip': data.get('zip_code', '') or secondary_data.get('zip_code', ''),
            'city': data.get('city', '') or secondary_data.get('city', ''),
            'country_id': country and country.id or False,
            'is_company': is_company,
            'comment': comment,
            # TODO: eventually if needed:
            # lang
            # street_number and street_number2 instead if base_address_extended is installed?
            # state_id -> US, from the region field?
            # property_account_position_id, property_payment_term_id
        }
        if address_type:
            values.update({
                'type': address_type,
                'parent_id': parent_id,
            })
        return self.env['res.partner'].with_context(skip_child_check=True).create(values)

    def update_partner_address(self, partner, data, secondary_data, is_company=False):
        # updates the partner data if anything in the address changed
        # data is the primary source, secondary is used only if primary is empty (e.g. customer and billing sections)

        if not partner:
            return False
        create_new = False

        # if invoice or delivery address changes, update the existing one to type =other
        # and create a new one
        if partner.type and partner.type in ['invoice', 'delivery']:
            create_new = True

        if is_company:
            name = data.get('company', '')
        else:
            name = '{first_name} {middle_name} {last_name}'.format(first_name=data.get('first_name', ''),
                                                                   middle_name=data.get('middle_name', ''),
                                                                   last_name=data.get('last_name', ''))
        zip_code = data.get('zip_code') or secondary_data.get('zip_code')
        city = data.get('city', '') or secondary_data.get('city', '')
        country_code = data.get('country_code', '') or secondary_data.get('country_code', '')
        country = self.env['res.country'].search([('code', '=', country_code)], limit=1)
        address1 = data.get('address1', '') or secondary_data.get('address1', '')
        address2 = data.get('address2', '') or secondary_data.get('address2', '')
        address_supplement = data.get('address_supplement', '') or secondary_data.get('address_supplement', '')
        street2 = '{address2} {address_supplement}'.format(address2=address2, address_supplement=address_supplement)
        phone = data.get('phone', '') or secondary_data.get('phone', '')
        mobile = data.get('mobile', '') or secondary_data.get('mobile', '')
        if partner.zip != zip_code or \
                partner.city != data.get('city') or \
                partner.street != address1 or \
                partner.street2 != street2 or \
                partner.country_id != country or \
                partner.phone != phone or \
                partner.mobile != mobile or \
                partner.name != name:
            if create_new:
                new_partner = self.create_partner_address(data=data,
                                                          secondary_data=secondary_data,
                                                          address_type=partner.type,
                                                          is_company=False,
                                                          parent_id=partner.parent_id and partner.parent_id.id or False)
                partner.write({'type': 'other'})
                partner = new_partner
            else:
                partner.write({
                    'name': name or partner.name,
                    'phone': phone or partner.phone or '0000000000',
                    'mobile': mobile or partner.mobile,
                    'street': address1 or partner.street,
                    'street2': street2 or partner.street2,
                    'zip': zip_code or partner.zip,
                    'city': city or partner.city,
                    'country_id': (country and country.id) or (partner.country_id or partner.country_id.id),
                })
        return partner

    def create_order_line_from_channable(self, sale_order, line_data, product, is_delivery):
        SaleOrderLine = self.env['sale.order.line']
        unit_price = float(line_data.get('price', 0))
        quantity = float(line_data.get('quantity', 0))
        line_title = line_data.get('title', '')
        uom_id = product and product.uom_id and product.uom_id.id or False

        product_data = {
            'order_id': sale_order.id,
            'product_id': product and product.id or False,
            'company_id': sale_order.company_id.id,
            'product_uom_qty': quantity,
            'product_uom': uom_id,
            'price_unit': unit_price,
            'name': line_title,
        }
        temporary = SaleOrderLine.new(product_data)
        temporary.product_id_change()
        temporary._onchange_discount()
        values = SaleOrderLine._convert_to_write({name: temporary[name] for name in temporary._cache})
        values.update({
            'order_id': sale_order.id,
            'product_uom_qty': quantity,
            'price_unit': unit_price,
            'channable_line_id': line_data.get('id'),
            'is_delivery': is_delivery,
            # 'tax_id': tax_ids and [(6, 0, tax_ids.ids)] or [(6, 0, [])],
        })
        line = SaleOrderLine.create(values)
        line._compute_amount()
        line._compute_tax_id()
        # compute the unit price from the total price that Channable sends (tax included)
        if line.tax_id and line.tax_id.amount and sale_order.company_id and sale_order.company_id.channable_prices_contain_tax:
            unit_price = line.price_unit / (1 + (line.tax_id.amount / 100.00))
            line.price_unit = unit_price
        return line

    @api.model
    def cron_update_status_in_channable(self):
        if self.search(['|', ('channable_to_update_cancel', '=', True), ('channable_to_update_shipped', '=', True)]):
            CeleryTask = self.env['celery.task']
            domain = [
                ('model', '=', self._name),
                ('method', '=', 'update_status_in_channable'),
                ('state', '=', CELERY_STATE_PENDING)
            ]
            if CeleryTask.search_count(domain) == 0:
                celery = {
                    'countdown': 1,
                    'retry': True,
                    'max_retries': 0,
                    'interval_start': 5,
                    'queue': 'high.priority',
                }
                celery_task_vals = {'ref': 'Update Order Status To Channable'}
                CeleryTask.call_task(self._name, 'update_status_in_channable', celery=celery, celery_task_vals=celery_task_vals)
        return True

    @api.model
    def update_status_in_channable(self, task_uuid, **kwargs):
        updated_orders_count = 0
        update_log = ''
        for order_to_cancel in self.search([('channable_order_id', '!=', False), ('channable_to_update_cancel', '=', True)]):
            result = order_to_cancel.update_status_canceled_channable()
            updated_orders_count += 1
            update_log += "Canceled order: %s\n" % order_to_cancel.name
        for order_to_update in self.search([('channable_order_id', '!=', False), ('channable_to_update_shipped', '=', True)]):
            result = order_to_update.update_status_shipped_channable()
            update_log += "Updated order: %s\n" % order_to_update.name
            updated_orders_count += 1

        msg = 'Channable: updated status for %s orders.\n%s' % (str(updated_orders_count), update_log)
        _logger.info(msg)
        return msg

    def update_status_canceled_channable(self):
        if not self.channable_order_id:
            raise UserError(_('This Order Is Not a Channable Order, Unable To Update!'))
        order_response = self.env.user.company_id.channable_request(method="GET",
                                                              endpoint="/orders/%s" % self.channable_order_id,
                                                              payload={},
                                                              timeout=120)
        if order_response.get('order', {}).get('status_shipped', False) == 'cancelled':
            self.write({
                'channable_to_update_cancel': False,
                'channable_order_status': 'cancelled',
            })
        else:
            self.env.user.company_id.channable_request(method="POST",
                                                        endpoint="/orders/%s/cancel" % self.channable_order_id,
                                                        payload={},
                                                        timeout=120)


    def update_status_shipped_channable(self):
        if not self.channable_order_id:
            raise UserError(_('This Order Is Not a Channable Order, Unable To Update!'))
        endpoint = '/orders/{order_id}/shipment'.format(order_id=self.channable_order_id)
        tracking_code = ''
        transporter = ''
        # concatenate all tracking codes if they exist
        for done_picking in self.mapped('picking_ids').filtered(lambda p: p.state == 'done'):
            if done_picking.carrier_tracking_ref:
                tracking_code = tracking_code + done_picking.carrier_tracking_ref + ','
            if done_picking.carrier_id and done_picking.carrier_id.channable_transporter_code:
                transporter = done_picking.carrier_id.channable_transporter_code
            elif done_picking.carrier_id:
                transporter = done_picking.carrier_id.name
            if tracking_code:
                tracking_code = tracking_code[:-1]
        if not tracking_code:
            tracking_code = 'null'
        if not transporter:
            transporter = 'null'
        payload = {
            'tracking_code': tracking_code,
            'transporter': transporter,
        }
        order_response = self.env.user.company_id.channable_request(method="GET",
                                                              endpoint="/orders/%s" % self.channable_order_id,
                                                              payload={},
                                                              timeout=120)
        if order_response.get('order', {}).get('status_shipped', False) != 'not_shipped':
            self.write({
                'channable_to_update_shipped': False,
                'channable_order_status': 'shipped',
            })
        else:
            response = self.env.user.company_id.channable_request(method="POST",
                                                                endpoint=endpoint,
                                                                payload=payload,
                                                                timeout=120)

        return True

    def action_cancel(self):
        res = super(SaleOrder, self).action_cancel()
        self.filtered(lambda o: o.channable_order_id).write({'channable_to_update_cancel': True})
        return res

    def action_force_update_channable(self):
        self.update_status_shipped_channable()

    def action_force_cancel_channable(self):
        self.update_status_canceled_channable()

    def action_view_in_channable(self):
        if self.channable_order_id:
            if self.company_id and self.company_id.channable_company_id and self.company_id.channable_project_id:
                url = 'https://app.channable.com/companies/{company_id}/projects/{project_id}/orders/{order_id}'.format(company_id=self.company_id.channable_company_id,
                                                                                                                        project_id=self.company_id.channable_project_id,
                                                                                                                        order_id=self.channable_order_id)
                return {
                    "type": "ir.actions.act_url",
                    "url": url,
                    "target": "new",
                }

    def process_channel_payment(self):
        for record in self.search([('channel_process_payment', '=', True),('channable_order_id','!=',False)]):
            journal_id = self.env['account.journal'].search([('channable_channel_name', 'ilike', record.channable_payment_method)], limit=1)
            if not journal_id:
                continue
            try:
                for invoice in record.invoice_ids.filtered(lambda i: i.state != 'cancel' and i.invoice_payment_state != 'paid'):
                    invoice.action_register_payment_direct(journal_id=journal_id.id)
                record.write({
                    'channel_process_payment': False
                })
            except Exception as e:
                msg = "Prestashop payment creation error: %s %s" % (str(e), record.name)
                _log_logging(self.env, msg, 'process_channel_payment', record.id)
                _logger.warn(msg)
                continue
        return super(SaleOrder, self).process_channel_payment()

    def _get_sale_order_has_issues(self):
        vals = super(SaleOrder, self)._get_sale_order_has_issues()
        orders = self.search([('channable_order_id', '!=', False), ('state', '=', 'sale')]).filtered(lambda o: not o.invoice_ids.filtered(lambda i: i.invoice_payment_state == 'paid'))
        if orders:
            vals.append({
                'name': 'Channable order confirmed but invoice not marked as paid',
                'orders': orders.mapped(lambda o: (o.id, o.name))
            })
        not_shipped_orders = self.search([('channable_order_id', '!=', False), ('all_qty_delivered', '=', True), ('channable_order_status', '!=', 'shipped')])
        if not_shipped_orders:
            vals.append({
                'name': 'Channable order delivered but status not marked as shipped',
                'orders': not_shipped_orders.mapped(lambda o: (o.id, o.name))
            })

        return vals

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    channable_line_id = fields.Char(string="Channable Order Line ID", copy=False)
