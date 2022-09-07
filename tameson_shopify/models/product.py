
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import time, json, requests
from odoo.addons.shopify_ept import shopify
from odoo.tools.float_utils import float_compare
from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT as DSDF

import logging
_logger = logging.getLogger(__name__)


def process_export(lines):
    vals_list = []
    for line in lines:
        try:
            line_data = json.loads(line)
            sku = line_data['sku']
            if not sku:
                continue
            vals_list.append({
                'name': sku,
                'inventory_item_id': line_data['inventory_item_id'],
                'variant_id': line_data['variant']['variant_id'],
                'shopify_tmpl_id': line_data['variant']['product']['product_id'],
                'available': line_data['inventoryLevel']['available']
            })
        except Exception as e:
            continue
    return vals_list


class ShopifyProcessImportExport(models.TransientModel):
    _inherit = 'shopify.process.import.export'

    @api.model
    def update_stock_in_shopify(self, ctx={}):
        if self.shopify_instance_id:
            instance = self.shopify_instance_id
        elif ctx.get('shopify_instance_id'):
            instance_id = ctx.get('shopify_instance_id')
            instance = self.env['shopify.instance.ept'].browse(instance_id)
        location = self.env['shopify.location.ept'].search([('instance_id','=',instance.id)], limit=1)
        if not location:
            raise UserError("No location found for instance %s" % instance.name)
        query_all_sku_available = """
mutation {
    bulkOperationRunQuery(
        query: \"\"\"
            {
                inventoryItems {
                    edges {
                        node {
                            inventory_item_id: legacyResourceId
                            variant {
                                variant_id: legacyResourceId
                                product {
                                    product_id: legacyResourceId
                                }
                            }
                            sku
                            inventoryLevel (locationId: "gid://shopify/Location/%s") {
                                available
                            }
                        }
                    }
                }
            }
        \"\"\"
        ) {
        bulkOperation {
            id
            status
        }
        userErrors {
            field
            message
        }
    }
}""" % location.shopify_location_id

        # with shopify.Session.temp(instance.shopify_host, "2021-04", instance.shopify_password):
        session = shopify.Session(instance.shopify_host, "2021-04", instance.shopify_password)
        shopify.ShopifyResource.activate_session(session)
        query_result = json.loads(shopify.GraphQL().execute(query_all_sku_available))
        _logger.info("ShopifyStock: Start %s" % (instance.name))

    @api.model
    def compare_and_sync(self, instance_id, gid):
        instance = self.env['shopify.instance.ept'].browse(instance_id)
        _logger.info("ShopifyStock: webhook received %s" % (instance.name))
        session = shopify.Session(instance.shopify_host, "2021-04", instance.shopify_password)
        shopify.ShopifyResource.activate_session(session)
        api_url_query = '''query {
            node(id: "%s") {
                ... on BulkOperation {
                url
                }
            }
        }''' % gid
        query_result = json.loads(shopify.GraphQL().execute(api_url_query))
        shopify.ShopifyResource.clear_session()
        url = query_result['data']['node']['url']
        data = requests.get(url)
        data.encoding = data.apparent_encoding
        lines = data.text.split("\n")
        levels = tuple(self.env['shopify.stock.level'].create(process_export(lines)).ids)
        _logger.info("ShopifyStock: downloaded export %d" % len(levels))
        missing_map_query = '''
select pp.id product_id, pt.id tmpl_id, sl.name sku, sl.inventory_item_id, sl.variant_id, sl.shopify_tmpl_id 
from shopify_stock_level sl
left join product_product pp on pp.default_code = sl.name
left join product_template pt on pp.product_tmpl_id = pt.id
left join shopify_product_product_ept sp on sp.product_id = pp.id and sp.shopify_instance_id = %d
where sp.id is null and sl.id in %s''' % (instance.id, str(levels))
        self.env.cr.execute(missing_map_query)
        missing_map_data = self.env.cr.fetchall()
        self.with_delay().create_missing_maps(missing_map_data, instance)
        qty_mismatch_query = '''
select pp.id product_id
from shopify_stock_level sl
left join product_product pp on pp.default_code = sl.name
left join shopify_product_product_ept sp on sp.product_id = pp.id and sp.shopify_instance_id = %d
where round(sl.available::numeric, 2) != round(pp.minimal_qty_available_stored::numeric, 2)
and sl.id in %s''' % (instance.id, str(levels))
        self.env.cr.execute(qty_mismatch_query)
        qty_mismatch_data = self.env.cr.fetchall()
        mismatch_products = [row[0] for row in qty_mismatch_data]
        chunked_mismatch = [mismatch_products[i:i + 100] for i in range(0, len(mismatch_products), 100)]
        for cm in chunked_mismatch:
            self.with_delay().sync_mismatch_qty(cm, instance)
        return True

    def create_missing_maps(self, missing_map_data, instance):
        map_obj = self.env['shopify.product.template.ept']
        for product_id, tmpl_id, sku, inventory_item_id, variant_id, shopify_tmpl_id  in missing_map_data:
            if not sku or not product_id:
                continue
            map_data = {
                'shopify_instance_id': instance.id,
                'product_tmpl_id': tmpl_id,
                'shopify_tmpl_id': shopify_tmpl_id,
                'inventory_management': "shopify",
                'name': self.env['product.template'].browse(tmpl_id).name,
                'exported_in_shopify': True,
                'website_published': True,
                'total_variants_in_shopify': 1,
                'shopify_product_ids': [(0, 0, {
                    'shopify_instance_id': instance.id,
                    'exported_in_shopify': True,
                    'inventory_management': "shopify",
                    'variant_id': variant_id,
                    'inventory_item_id': inventory_item_id,
                    'product_id': product_id,
                    'name': self.env['product.product'].browse(product_id).name,
                    'default_code': sku
                })]
            }
            map_obj.create(map_data)
        return True

    def update_stock_all_shop(self):
        lasthour = datetime.now() - timedelta(hours=2)
        lasthour_formatted = lasthour.strftime(DSDF)
        domain = ['|', ('create_date', '>', lasthour_formatted),
                  ('write_date', '>', lasthour_formatted)]
        to_update_products = self.env['stock.move.line'].search(domain).mapped(
            'product_id') + self.env['stock.move'].search(domain).mapped('product_id').ids
        bom_product_query = '''
SELECT DISTINCT ppl.id FROM mrp_bom_line bl
    LEFT JOIN mrp_bom mb ON mb.id = bl.bom_id
    LEFT JOIN product_product ppl mb.product_tmpl_id = ppl.product_tmpl_id
WHERE bl.product_id IN (%s)''' % ','.join(map(str, to_update_products))
        self.env.cr.execute(bom_product_query)
        bom_products = [item[0] for item in self.env.cr.fetchall()]
        to_update = set(to_update_products + bom_products)
        chunked_mismatch = [to_update[i:i + 100] for i in range(0, len(to_update), 100)]
        for instance in self.env['shopify.instance.ept'].search([]):
            for cm in chunked_mismatch:
                self.with_delay().sync_mismatch_qty(cm, instance)
    
    def sync_mismatch_qty(self, mismatch_products, instance):
        shopify_product_obj = self.env['shopify.product.product.ept']
        if mismatch_products:
            product_id_array = sorted(mismatch_products)
            shopify_products = shopify_product_obj.with_context(is_process_from_selected_product=True).export_stock_in_shopify(
                instance, product_id_array)
            if shopify_products:
                instance.write(
                    {'shopify_last_date_update_stock': shopify_products[0].last_stock_update_date})
        else:
            _logger.info("No products to export stock.....")
            instance.write({'shopify_last_date_update_stock': datetime.now()})
        return True


class ShopifyProductProductEpt(models.Model):
    _inherit = "shopify.product.product.ept"

    def check_stock_type(self, instance, product_ids, prod_obj, warehouse):
        product_stock_dict = {}
        product_data = product_ids.read(['minimal_qty_available_stored'])
        for i in product_data:
            product_stock_dict.update({i.get('id'): i.get('minimal_qty_available_stored')})
        return product_stock_dict