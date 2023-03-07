import werkzeug
import werkzeug.wrappers

from odoo import http
from odoo.http import request


class VariantController(http.Controller):
    @http.route(
        ["/stock/ups_labels/<string:picking_ids>"],
        type="http",
        auth="user",
        methods=["GET"],
        website=True,
    )
    def stock_ups_labels(self, picking_ids, **kw):
        picking_obj = request.env["stock.picking"]
        pickings = picking_obj.browse([int(s) for s in picking_ids.split(",")])

        response = werkzeug.wrappers.Response()
        response.mimetype = "application/pdf"
        response.data = pickings.get_merged_ups_labels()

        return response

    @http.route(
        ["/stock/delivery_labels/<string:picking_ids>"],
        type="http",
        auth="user",
        methods=["GET"],
        website=True,
    )
    def stock_delivery_labels(self, picking_ids, **kw):
        picking_obj = request.env["stock.picking"]
        pickings = picking_obj.browse([int(s) for s in picking_ids.split(",")])
        pickings.generate_non_ups_labels()

        response = werkzeug.wrappers.Response()
        response.mimetype = "application/pdf"
        response.data = pickings.get_merged_labels()

        return response
