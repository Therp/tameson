###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

import logging

from gql import gql
from requests.exceptions import ConnectionError

from odoo import fields, models
from odoo.exceptions import UserError

from .pimcore_request import GqlQueryBuilder, PimcoreRequest

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
    "eur": {"field": "PriceEUR", "getter": static_getter},
    "gbp": {"field": "PriceGBP", "getter": static_getter},
    "usd": {"field": "PriceUSD", "getter": static_getter},
    "image": {
        "field": 'Images {... on asset {assetThumb: fullpath(thumbnail: "product_main")}}',
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
    "published": {"field": "published", "getter": static_getter},
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
    "pack_model": {"field": "PackModel", "getter": static_getter},
    "pack_factor": {"field": "PackFactor", "getter": static_getter},
    "sticker_barcode": {"field": "StickerBarcode", "getter": static_getter},
    "max_qty_order": {"field": "maximumQuantityToOrder", "getter": static_getter},
    "min_qty_order": {"field": "minimumQuantityToOrder", "getter": static_getter},
    "supplier_series": {"field": "SupplierSeries", "getter": static_getter},
    "supplier_shipping_type": {
        "field": "SupplierShippingType",
        "getter": static_getter,
    },
    "supplier_package_qty": {"field": "SupplierPackageQty", "getter": static_getter},
    "additional_cost": {"field": "AdditionalCost", "getter": static_getter},
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
    limit = fields.Integer(string="Pull limit", default=100)
    concurrent = fields.Integer(string="Concurrent connections", default=50)

    def action_cron_fetch_products(self):
        for record in self.search([]):
            record.action_fetch_products_jobs()

    def action_fetch_products(self):
        self.ensure_one()
        pim_request = PimcoreRequest(self.api_host, self.api_name, self.api_key)
        product_query = GqlQueryBuilder("getProductListing", "edges", product_nodes)

        try:
            record_count = (
                pim_request.execute(
                    gql("{getProductListing(published: false) {totalCount}}")
                )
                .get("getProductListing", {})
                .get("totalCount", 0)
            )
            result = pim_request.execute_async(
                product_query, 0, record_count, self.limit, self.concurrent
            )
        except ConnectionError:
            raise UserError("Unable to connect with Pimcore server.")

        all_result = product_query.parse_results(result)
        lines_ids = []
        for node in all_result:
            data = node.get("node")
            try:
                val = {
                    key: product_nodes[key]["getter"](val) for key, val in data.items()
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

    def action_cron_fetch_new(self):
        for record in self.search([]):
            record.action_fetch_new()

    def action_fetch_new(self):
        self.ensure_one()
        last_mdate = (
            self.env["product.template"]
            .search(
                [("modification_date", ">", 0)],
                order="modification_date DESC",
                limit=1,
            )
            .modification_date
        )
        pim_request = PimcoreRequest(self.api_host, self.api_name, self.api_key)
        filter = '\\"o_modificationDate\\" : {\\"$gt\\": \\"%.1f\\"}' % last_mdate
        last_m_product_query = GqlQueryBuilder(
            "getProductListing", "edges", product_nodes, filters=[filter]
        )
        result = pim_request.execute(last_m_product_query.get_query())
        all_result = last_m_product_query.parse_results(result)
        lines_ids = []
        for node in all_result:
            data = node.get("node")
            try:
                val = {
                    key: product_nodes[key]["getter"](val) for key, val in data.items()
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

    def action_fetch_products_jobs(self):
        self.ensure_one()
        response_obj = self.env["pimcore.product.response"].create(
            {"config_id": self.id, "type": "full"}
        )
        pim_request = PimcoreRequest(self.api_host, self.api_name, self.api_key)
        query = GqlQueryBuilder(
            "getProductListing",
            "edges",
            {"id": {"field": "id", "getter": static_getter}},
        )
        params = 'first: %d, sortBy: "o_id",  sortOrder: "%s"'
        try:
            first_id = query.parse_results(
                pim_request.execute(query.get_query(params % (1, "ASC")))
            )[0]
            last_id = query.parse_results(
                pim_request.execute(query.get_query(params % (1, "DESC")))
            )[0]
            first_id = int(first_id["node"]["id"])
            last_id = int(last_id["node"]["id"])
        except Exception:
            raise UserError("No valid first, last product ID from pimcore.")
        for pos in range(first_id, last_id, self.limit):
            self.with_delay().request_products_data(pos, response_obj)

    def request_products_data(self, pos, res):
        params = 'sortBy: "o_id",  sortOrder: "ASC"'
        pim_request = PimcoreRequest(self.api_host, self.api_name, self.api_key)
        product_query = GqlQueryBuilder(
            "getProductListing",
            "edges",
            product_nodes,
            filters=[
                '\\"$and\\": [{\\"o_id\\": {\\"$gte\\": \\"%d\\"}}, {\\"o_id\\": {\\"$lt\\": \\"%d\\"}}]'
                % (pos, pos + self.limit)
            ],
        )
        result = pim_request.execute(product_query.get_query(params))
        result = product_query.parse_results(result)
        lines_ids = []
        for node in result:
            data = node.get("node")
            val = {key: product_nodes[key]["getter"](val) for key, val in data.items()}
            val["response_id"] = res.id
            if val["full_path"] and val["full_path"].startswith("/TestFolder"):
                continue
            lines_ids.append(val)
        self.env["pimcore.product.response.line"].create(lines_ids)
