
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from datetime import datetime, timezone

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta

from odoo.addons.celery.models.celery_task import STATE_PENDING as CELERY_STATE_PENDING
from .prestashop_request import PrestashopRequest

import logging
_logger = logging.getLogger(__name__)
from pprint import pformat

DATEFORMAT = "%Y-%m-%d %H:%M:%S"

class PrestashopConfig(models.Model):
    _name = 'prestashop.config'
    _description = 'Prestashop Configuration'

    _rec_name = 'name'
    _order = 'name ASC'

    name = fields.Char(string='Shop name', required=True, copy=False)
    active = fields.Boolean(default=True)    
    url = fields.Char(string='Shop url', required=True, copy=False)
    key = fields.Char(string='API key', required=True, copy=False)
    shop_group = fields.Char(string='Shop Group ID', required=True, default="1")
    sync_days = fields.Integer(string='Sync order last n days',default=30)   
    batch_size = fields.Integer(string='Order request batch size',default=500)   
    discount_product_id = fields.Many2one(string='Discount Product', comodel_name='product.product', ondelete='restrict', required=True)
    source_id = fields.Many2one(string='Source', comodel_name='utm.source', ondelete='restrict')
    price_def_allowed = fields.Float(string='Allowed price difference', default=0.02, digits='Product Price')


    def cron_get_orders(self):
        CeleryTask = self.env['celery.task']
        domain = [
            ('model', '=', self._name),
            ('method', '=', 'get_orders'),
            ('state', '=', CELERY_STATE_PENDING)
        ]
        get_orders_celery = {
            'countdown': 1,
            'retry': True,
            'max_retries': 3,
            'interval_start': 5,
            'queue': 'high.priority',
        }
        for Config in self.search([]):
            get_order_ref = 'Get Orders From Prestashop config_id: %d' % Config.id
            if CeleryTask.search_count(domain + [('ref','=', get_order_ref)]) == 0:
                CeleryTask.call_task(self._name, 'get_orders', config=Config.id, celery=get_orders_celery, celery_task_vals={'ref': get_order_ref})
        return True

    def get_orders(self, task_uuid, config, **kwargs):
        self = self.browse(config)
        Sale = self.env['sale.order']
        SaleLine = self.env['sale.order.line']
        CeleryTask = self.env['celery.task']
        celery = {
            'countdown': 1,
            'retry': True,
            'max_retries': 2,
            'interval_start': 1,
        }
        celery_task_vals = {'ref': 'Create/update Order From Prestashop'}

        # from_time = Sale.search([('prestashop_config_id','=',self.id)], order='prestashop_date_upd DESC', limit=1).prestashop_date_upd
        now_dt = datetime.now(tz=timezone.utc) + relativedelta(hours=2)
        to_time = now_dt.strftime(DATEFORMAT)
        from_time = (now_dt + relativedelta(days=-self.sync_days)).strftime(DATEFORMAT)

        request_params = {
            'display': '[id,id_address_delivery,id_address_invoice,id_cart,\
                id_currency,id_lang,id_customer,id_carrier,current_state,module,\
                date_upd,id_shop,total_paid_tax_excl,total_shipping_tax_excl,\
                reference,user_invoice_email,ups_id_access_point,ups_country_iso,\
                user_reference,total_discounts_tax_excl]',
            'filter[date_upd]': '[%s,%s]' % (from_time, to_time),
            'filter[date_add]': '[2020-12-22 00:00:00,%s]' % (to_time),
            'date': '1',
            'sort': '[date_upd_DESC]'
        }
        Request = PrestashopRequest(self.url, self.key, self.shop_group)
        all_orders = []
        if self.batch_size:
            offset = 0
            orders = Request.get('orders', params=request_params,limit='%d,%d' % (offset,self.batch_size)).get('orders', {})
            while orders:
                order_list = orders.get('order',[])
                if isinstance(order_list, dict):
                    order_list = [order_list]
                all_orders.extend(order_list)
                offset += self.batch_size
                orders = Request.get('orders', params=request_params, limit='%d,%d' % (offset,self.batch_size)).get('orders', {})
        else:
            orders = Request.get('orders', params=request_params).get('orders', {})
            if orders:
                all_orders = orders.get('order',[])
                if isinstance(all_orders, dict):
                    all_orders = [all_orders]
        all_customer_ids = []
        all_address_ids = []
        all_carrier_ids = []
        all_order_ids = []
        for order in all_orders:
            all_order_ids.append(order.get('id', '0'))
            all_customer_ids.append(order.get('id_customer', '0'))
            all_address_ids.extend([order.get('id_address_delivery', '0'), order.get('id_address_invoice', '0')])
            all_carrier_ids.append(order.get('id_carrier', '0'))
        
        order_details_params = {
            'display': '[id_order,product_name,product_quantity,unit_price_tax_excl,product_reference]',
            'sort': '[id_order_DESC]',
            'filter[id_order]': '[%s]' % '|'.join(set(all_order_ids))
        }
        order_details = Request.get('order_details', params=order_details_params).get('order_details', {})
        order_rows = {}
        if order_details:
            order_rows_data = order_details.get('order_detail', [])
            if isinstance(order_rows_data, dict):
                order_rows_data = [order_rows_data]
            for row in order_rows_data:
                id_order = row['id_order']
                if id_order not in order_rows:
                    order_rows[id_order] = [row]
                else:
                    order_rows[id_order].append(row)
        all_customer_data = Request.get_by_ids('customers',ids=all_customer_ids, fields='[id,id_lang,lastname,firstname,email,company]')
        all_address_data = Request.get_by_ids('addresses',ids=all_address_ids)
        all_country_data = Request.get_by_ids('countries', ids='all', fields='[id,iso_code]')
        all_states_data = Request.get_by_ids('states', ids='all', fields='[id,iso_code]')
        updated = 0
        created = 0
        skipped = 0
        for order in all_orders:
            order_id = order.get('id', False)
            current_state = order.get('current_state', False)
            try:
                order.update(order_rows=order_rows.get(order_id,[]))
                sale_order = Sale.search([('prestashop_config_id','=',self.id),('prestashop_id','=',order_id)], limit=1)
                if sale_order:
                    if current_state in ('6', '146'):
                        CeleryTask.call_task('sale.order', 'update_from_prestashop', so_id=sale_order.id, order=order, celery=celery, 
                            celery_task_vals={'ref': 'Update existing order from prestashop: %s' % sale_order.name})
                    updated += 1
                #skip states canceled,payment process started, awaiting payment (adyen)
                elif current_state in ('6', '13', '152'):
                    skipped += 1
                else:
                    customer = all_customer_data[order.get('id_customer', '0')]
                    delivery = order.get('id_address_delivery', '0')
                    invoice = order.get('id_address_invoice', '0')
                    carrier = order.get('id_carrier', '0')
                    invoice_data = all_address_data.get(invoice, {})
                    delivery_data = all_address_data.get(delivery, {})
                    delivery_country_code = all_country_data.get(delivery_data.get('id_country', '0'),{}).get('iso_code', '')
                    invoice_country_code = all_country_data.get(invoice_data.get('id_country', '0'),{}).get('iso_code', '')
                    delivery_state_code = all_states_data.get(delivery_data.get('id_state', '0'),{}).get('iso_code', '')
                    invoice_state_code = all_states_data.get(invoice_data.get('id_state', '0'),{}).get('iso_code', '')
                    delivery_data.update(country_code=delivery_country_code, state_code=delivery_state_code)
                    invoice_data.update(country_code=invoice_country_code, state_code=invoice_state_code)
                    data = {
                        'order': order,
                        'customer': customer,
                        'delivery': delivery_data,
                        'invoice': invoice_data,
                        'config_id': config
                    }
                    CeleryTask.call_task('sale.order', 'create_from_prestashop', order=data, celery=celery, 
                        celery_task_vals={'ref': 'Create order from prestashop id: %s email: %s' % (order['id'], customer['email'])})
                    created += 1
            except Exception as e:
                raise Exception("%s\n%s" % (str(e), order_id))
        return "Pulled from API: %d\nUpdated orders: %d\nCreated orders: %d\nSkipped orders: %d" % (len(all_orders), updated, created, skipped)
    
    def cron_sync_order_status(self):
        CeleryTask = self.env['celery.task']
        domain = [
            ('model', '=', self._name),
            ('state', '=', CELERY_STATE_PENDING)
        ]
        sync_orders_celery = {
            'countdown': 1,
            'retry': True,
            'max_retries': 3,
            'interval_start': 5,
            'queue': 'high.priority',
        }

        for Config in self.search([]):
            sync_order_ref = 'Sync Order status From Prestashop config_id: %d' % Config.id
            mark_shipped_ref = 'Mark Order shipped to Prestashop config_id: %d' % Config.id
            if CeleryTask.search_count(domain + [('ref','=', sync_order_ref), ('method', '=', 'sync_order_status'),]) == 0:
                CeleryTask.call_task(self._name, 'sync_order_status', config=Config.id, celery=sync_orders_celery, celery_task_vals={'ref': sync_order_ref})
            if CeleryTask.search_count(domain + [('ref','=', mark_shipped_ref), ('method', '=', 'prestashop_mark_shipped'),]) == 0:
                CeleryTask.call_task(self._name, 'prestashop_mark_shipped', config=Config.id, celery=sync_orders_celery, celery_task_vals={'ref': mark_shipped_ref})
        return True

    def sync_order_status(self, task_uuid, config, **kwargs):
        celery = {
            'countdown': 1,
            'retry': True,
            'max_retries': 3,
            'interval_start': 5,
            'queue': 'celery',
        }

        CeleryTask = self.env['celery.task']
        self = self.browse(config)
        Sale = self.env['sale.order']
        from_date = datetime.now() - relativedelta(days=120)
        orders = Sale.search([('prestashop_config_id','=',config),('state','not in',('cancel','sale')),('create_date','>=',from_date)])
        prestashop_order_ids = orders.mapped('prestashop_id')
        Request = PrestashopRequest(self.url, self.key, self.shop_group)
        params = {
            'filter[id_order_state]': '[2]',
            'filter[id_order]': '[%s]' % '|'.join(prestashop_order_ids),
            'display': '[id_order]'
        }
        order_histories = Request.get('order_histories', params = params).get('order_histories', {})
        if order_histories:
            confirmed_prestashop_orders = order_histories.get('order_history', [])
            if isinstance(confirmed_prestashop_orders, dict):
                confirmed_prestashop_orders = [confirmed_prestashop_orders]
        else:
            confirmed_prestashop_orders = []
        confirmed_prestashop_order_ids = [oh['id_order'] for oh in confirmed_prestashop_orders]
        order_data_dict = Request.get_by_ids('orders', ids=prestashop_order_ids, fields='[id,module,total_paid_tax_incl]')
        for order in orders:
            data = order_data_dict[order.prestashop_id]
            if order.prestashop_id in confirmed_prestashop_order_ids or (data['module'] == 'ps_wirepayment' and not order.invoice_ids):
                CeleryTask.call_task('sale.order', 'prestashop_order_process', so_id=order.id, data=data, celery=celery, celery_task_vals={'ref': order.name})
        return True

    def prestashop_mark_shipped(self, task_uuid, config, **kwargs):
        self = self.browse(config)
        Request = PrestashopRequest(self.url, self.key, self.shop_group)
        Sale = self.env['sale.order']
        SuccessOrders = Sale.browse()
        ShippedOrders = Sale.search([
            ('prestashop_config_id','=',config),
            ('shipped_status_prestashop','=',False),
            ('state','=','sale'),
            '|',('force_all_qty_delivered','=',True),('all_qty_delivered','=',True)])
        sync_ship_params = [{
                'id': '', 
                'id_employee': '0',
                'id_order_state': '4', 
                'id_order': order.prestashop_id, 
                'date_add': ''
            } for order in ShippedOrders]
        if len(sync_ship_params) == 1:
            sync_ship_params = sync_ship_params[0]
        if sync_ship_params:
            response = Request.request.add('order_histories', content={'order_history': sync_ship_params})
            if response:
                response_orders = response.get('prestashop', {}).get('order_history', [])
                if isinstance(response_orders, dict):
                    response_orders = [response_orders]
            else:
                response_orders = []
            response_order_ids = [o['id_order'] for o in response_orders]
            SuccessOrders = ShippedOrders.filtered(lambda o: o.prestashop_id in response_order_ids)
            SuccessOrders.write({'shipped_status_prestashop': True})
        return True
