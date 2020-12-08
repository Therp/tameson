from prestapyt import PrestaShopWebServiceDict
from odoo.exceptions import UserError, ValidationError

import logging
_logger = logging.getLogger(__name__)
from pprint import pformat

data_map = {
    'countries': 'country',
    'customers': 'customer',
    'addresses': 'address',
    'carriers': 'carrier',
    'order_histories': 'order_history',
    'orders': 'order',
    'states': 'state'
}

class PrestashopRequest(object):
    def __init__(self, url, key, shop_group=None):
        self.request = PrestaShopWebServiceDict(url, key)
        self.shop_group = shop_group

    def get(self, endpoint, params={}, **kwargs):
        params.update(kwargs)
        # _logger.warn(endpoint)
        # _logger.warn(pformat(params))
        if self.shop_group:
            params.update(id_group_shop = self.shop_group)
        try:
            response = self.request.get(endpoint, options=params)
        except Exception as E:
            raise UserError(str(E))
        return response

    def get_by_ids(self, endpoint, id_field='id', ids=[], fields='full', **kwargs):
        params = {
            'display': fields,
        }
        if not ids == 'all':
            params.update({'filter[%s]'%id_field: '[%s]' % ('|'.join(set(ids)))})
        response = self.get(endpoint, params=params, **kwargs)
        response_dict = response.get(endpoint, {})
        if response_dict:
            response_list = response_dict.get(data_map[endpoint], [])
            if isinstance(response_list, dict):
                response_list = [response_list]
            result_dict = {obj['id']:obj for obj in response_list}
        else:
            result_dict = {}
        return result_dict
    