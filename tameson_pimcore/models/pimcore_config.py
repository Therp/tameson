# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

from gql import gql
from gql.transport import requests

from .pimcore_request import PimcoreRequest, GqlQueryBuilder

import logging

_logger = logging.getLogger(__name__)

static_getter = lambda v: v
float_getter = lambda v: isinstance(v, dict) and v.get("value", 0.0)
image_getter = lambda v: v and v[0].get("assetThumb", "")
bom_getter = lambda v: v and ",".join(
    map(lambda i: "%s,%s" % (i["element"]["SKU"], i["metadata"][0]["value"]), v)
)
single_field_m2one = lambda v: isinstance(v, dict) and list(v.items())[0][1]
single_field_m2many = lambda v: v and list(v[0].items())[0][1]

product_nodes = {
    "name": {"field": "Name", "getter": static_getter},
    "name_nl": {"field": 'Name (language: "nl")', "getter": static_getter},
    "name_fr": {"field": 'Name (language: "fr")', "getter": static_getter},
    "name_de": {"field": 'Name (language: "de")', "getter": static_getter},
    "name_es": {"field": 'Name (language: "es")', "getter": static_getter},
    "pimcore_id": {"field": "id", "getter": static_getter},
    "full_path": {"field": "fullpath", "getter": static_getter},
    "sku": {"field": "SKU", "getter": static_getter},
    "intrastat": {"field": "Intrastat", "getter": static_getter},
    "ean": {"field": "EAN", "getter": static_getter},
    "width": {"field": "Width {value}", "getter": float_getter},
    "height": {"field": "Height {value}", "getter": float_getter},
    "depth": {"field": "Depth {value}", "getter": float_getter},
    "weight": {"field": "Weight {value}", "getter": float_getter},
    "volume": {"field": "Volume {value}", "getter": float_getter},
    "modification_date": {"field": "modificationDate", "getter": static_getter},
    "wholesaleprice": {"field": "wholesalePrice", "getter": static_getter},
    "gbp": {"field": "PriceGBP", "getter": static_getter},
    "usd": {"field": "PriceUSD", "getter": static_getter},
    "image": {
        "field": 'Images {... on asset {assetThumb: fullpath(thumbnail: "")}}',
        "getter": image_getter,
    },
    "bom": {
        "field": "BOM {element {... on object_Product {SKU}} metadata {value}}",
        "getter": bom_getter,
    },
    "short_description": {"field": "shortDescription", "getter": static_getter},
    "use_up": {"field": "UseUp", "getter": static_getter},
    "supplier_part_number": {"field": "SupplierPartNumber", "getter": static_getter},
    "supplier_price": {"field": "SupplierPrice", "getter": static_getter},
    "supplier_price_currency": {
        "field": "SupplierPriceCurrency",
        "getter": static_getter,
    },
    "supplier_lead_time": {"field": "SupplierLeadTime", "getter": static_getter},
    "customer_lead_time": {"field": "CustomerLeadTime", "getter": static_getter},
    "backorder": {"field": "Backorder", "getter": static_getter},
    "oversized": {"field": "Oversized", "getter": static_getter},
    "non_returnable": {"field": "NonReturnable", "getter": static_getter},
    "imperial": {"field": "Imperial", "getter": static_getter},
    "brand_name": {
        "field": "Manufacturer{... on object_Brand{Name}}",
        "getter": single_field_m2one,
    },
    "manufacturer_name": {
        "field": "ManufacturerOrganisation{... on object_Organisation{Name}}",
        "getter": single_field_m2one,
    },
    "mpn": {"field": "MPN", "getter": static_getter},
    "web_sales": {"field": "active", "getter": static_getter},
    "origin_country": {"field": "OriginCountry", "getter": static_getter},
    "supplier_email": {
        "field": "Supplier {... on object_Organisation{email}}",
        "getter": single_field_m2one,
    },
    "replacement_sku": {
        "field": "ReplacementProduct {... on object_Product{SKU}}",
        "getter": single_field_m2one,
    },
    "categories": {
        "field": "categories {... on object_ProductCategory {fullpath}}",
        "getter": single_field_m2many,
    },
}


class PimcoreConfig(models.Model):
    _name = "pimcore.config"
    _description = "PimcoreConfig"

    _rec_name = "name"
    _order = "name ASC"

    name = fields.Char(required=True, copy=False)
    api_host = fields.Char(
        required=True,
    )
    api_name = fields.Char(
        required=True,
    )
    api_key = fields.Char(
        required=True,
    )
    active = fields.Boolean(default=True)
    limit = fields.Integer(string="Pull limit", default=300)

    def action_fetch_products(self):
        if not self:
            self = self.search([])
        for config in self:
            pim_request = PimcoreRequest(
                config.api_host, config.api_name, config.api_key
            )
            product_query = GqlQueryBuilder("getProductListing", "edges", product_nodes)
            record_count = (
                pim_request.execute(gql("{getProductListing {totalCount}}"))
                .get("getProductListing", {})
                .get("totalCount", 0)
            )
            result = pim_request.execute_async(ProductQ, 0, record_count, config.limit)
            all_result = product_query.parse_results(result)
            lines_ids = []
            for node in all_result:
                data = node.get("node")
                try:
                    val = {
                        key: product_nodes[key]["getter"](val)
                        for key, val in data.items()
                    }
                except Exception as e:
                    _logger.warning(str(e))
                    _logger.warning(data)
                    continue
                lines_ids.append((0, 0, val))
            if lines_ids:
                response_obj = self.env["pimcore.product.response"].create(
                    {"config_id": self.id, "type": "full"}
                )
                response_obj.write({"line_ids": lines_ids})

    def action_fetch_new(self):
        if not self:
            self = self.search([])
        for config in self:
            last_mdate = (
                self.env["product.template"]
                .search(
                    [("modification_date", ">", 0)],
                    order="modification_date DESC",
                    limit=1,
                )
                .modification_date
            )
            pim_request = PimcoreRequest(
                config.api_host, config.api_name, config.api_key
            )
            filter = '\\"o_modificationDate\\" : {\\"$gt\\": \\"%.1f\\"}' % last_mdate
            last_m_product_query = GqlQueryBuilder(
                "getProductListing", "edges", product_nodes, filters=[filter]
            )
            result = pim_request.execute(LastmProductQ.get_query())
            all_result = last_m_product_query.parse_results(result)
            lines_ids = []
            for node in all_result:
                data = node.get("node")
                try:
                    val = {
                        key: product_nodes[key]["getter"](val)
                        for key, val in data.items()
                    }
                except Exception as e:
                    _logger.warning(str(e))
                    _logger.warning(data)
                    continue
                lines_ids.append((0, 0, val))
            if lines_ids:
                response_obj = self.env["pimcore.product.response"].create(
                    {"config_id": self.id, "type": "new"}
                )
                response_obj.write({"line_ids": lines_ids})
