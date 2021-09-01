# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

from gql.transport import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from .pimcore_request import PimcoreRequest, GqlQueryBuilder
from gql import gql

import logging
_logger = logging.getLogger(__name__)

static_getter = lambda v: v
float_getter = lambda v: isinstance(v, dict) and v.get('value', 0.0)
image_getter = lambda v: len(v) and v[0].get('assetThumb', '')
bom_getter = lambda v: v and ','.join(map(lambda i: "%s,%s" % (i['element']['SKU'],i['metadata'][0]['value']), v))
single_field_m2one = lambda v: isinstance(v, dict) and list(v.items())[0][1]

product_nodes = {
    'name': {'field': 'Name', 'getter': static_getter},
    'name_nl': {'field': 'Name (language: "nl")', 'getter': static_getter},
    'name_fr': {'field': 'Name (language: "fr")', 'getter': static_getter},
    'name_de': {'field': 'Name (language: "de")', 'getter': static_getter},
    'name_es': {'field': 'Name (language: "es")', 'getter': static_getter},
    'pimcore_id': {'field': 'id', 'getter': static_getter},
    'full_path': {'field': 'fullpath', 'getter': static_getter},
    'sku': {'field': 'SKU', 'getter': static_getter},
    'intrastat': {'field': 'Intrastat', 'getter': static_getter},
    'ean': {'field': 'EAN', 'getter': static_getter},
    'width': {'field': 'Width {value}', 'getter': float_getter},
    'height': {'field': 'Height {value}', 'getter': float_getter},
    'depth': {'field': 'Depth {value}', 'getter': float_getter},
    'weight': {'field': 'Weight {value}', 'getter': float_getter},
    'volume': {'field': 'Volume {value}', 'getter': float_getter},
    'modification_date': {'field': 'modificationDate', 'getter': static_getter},
    'wholesaleprice': {'field': 'wholesalePrice', 'getter': static_getter},
    'gbp': {'field': 'PriceGBP', 'getter': static_getter},
    'usd': {'field': 'PriceUSD', 'getter': static_getter},
    'image': {'field': 'Images {... on asset {assetThumb: fullpath(thumbnail: "")}}', 'getter': image_getter},
    'bom': {'field': 'BOM {element {... on object_Product {SKU}} metadata {value}}', 'getter': bom_getter},
    'short_description': {'field': 'shortDescription', 'getter': static_getter},
    'use_up': {'field': 'UseUp', 'getter': static_getter},
    'supplier_part_number': {'field': 'SupplierPartNumber', 'getter': static_getter},
    'supplier_price': {'field': 'SupplierPrice', 'getter': static_getter},
    'supplier_price_currency': {'field': 'SupplierPriceCurrency', 'getter': static_getter},
    'supplier_lead_time': {'field': 'SupplierLeadTime', 'getter': static_getter},
    'customer_lead_time': {'field': 'CustomerLeadTime', 'getter': static_getter},
    'backorder': {'field': 'Backorder', 'getter': static_getter},
    'oversized': {'field': 'Oversized', 'getter': static_getter},
    'non_returnable': {'field': 'NonReturnable', 'getter': static_getter},
    'imperial': {'field': 'Imperial', 'getter': static_getter},
    'brand_name': {'field': 'Manufacturer{... on object_Brand{Name}}', 'getter': single_field_m2one},
    'manufacturer_name': {'field': 'ManufacturerOrganisation{... on object_Organisation{Name}}', 'getter': single_field_m2one},
    'mpn': {'field': 'MPN', 'getter': static_getter},
    'origin_country': {'field': 'OriginCountry', 'getter': static_getter},
    'supplier_email': {'field': 'Supplier {... on object_Organisation{email}}', 'getter': single_field_m2one},
    'replacement_sku': {'field': 'ReplacementProduct {... on object_Product{SKU}}', 'getter': single_field_m2one},
}
ProductQ = GqlQueryBuilder('getProductListing', 'edges', product_nodes)


class PimcoreConfig(models.Model):
    _name = 'pimcore.config'
    _description = 'PimcoreConfig'

    _rec_name = 'name'
    _order = 'name ASC'

    name = fields.Char(required=True, copy=False)
    api_host = fields.Char(required=True,)
    api_name = fields.Char(required=True,)
    api_key = fields.Char(required=True,)
    active = fields.Boolean(default=True)
    limit = fields.Integer(string='Pull limit', default=300)

    def action_fetch_products(self):
        Request = PimcoreRequest(self.api_host, self.api_name, self.api_key)
        LineModel = self.env['pimcore.product.response.line']
        Response = self.env['pimcore.product.response'].create({'config_id': self.id})
        record_count = Request.execute(gql('{getProductListing {totalCount}}')).get('getProductListing', {}).get('totalCount', 0)
        result = Request.execute_async(ProductQ, 0, record_count, self.limit)
        all_result = ProductQ.parse_results(result)
        lines_ids = []
        for node in all_result:
            data = node.get('node')
            try:
                val = {key: product_nodes[key]['getter'](val) for key, val in data.items()}
            except Exception as e:
                _logger.warning(str(e))
                _logger.warning(data)
                continue
            lines_ids.append((0, 0, val))
        Response.write({
            'line_ids': lines_ids
        })
    
    def action_fetch_new(self):
        Request = PimcoreRequest(self.api_host, self.api_name, self.api_key)
        totalCount = Request.execute(gql('{getProductListing {totalCount}}')).get('getProductListing', {}).get('totalCount', 0)
        SkuQ = GqlQueryBuilder('getProductListing', 'edges', {'sku': {'field': 'SKU'}})
        result = Request.execute_async(SkuQ, 0, totalCount, 1000)
        all_result = SkuQ.parse_results(result)
        skus = [node['node']['sku'] for node in all_result]

        data = Request.execute(ProductQ.filter_by_skus(skus[:2000]))

    def action_fetch_new_by_creation(self):
        Request = PimcoreRequest(self.api_host, self.api_name, self.api_key)
        totalCount = Request.execute(gql('{getProductListing {totalCount}}')).get('getProductListing', {}).get('totalCount', 0)