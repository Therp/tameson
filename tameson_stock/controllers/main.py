from odoo import http
from odoo.http import request

import werkzeug
import werkzeug.wrappers


class VariantController(http.Controller):
    @http.route(['/stock/ups_labels/<string:picking_ids>'], type='http', auth='user', methods=['GET'], website=True)
    def stock_ups_labels(self, picking_ids, **kw):
        picking_obj = request.env['stock.picking']
        pickings = picking_obj.browse([int(s) for s in picking_ids.split(',')])

        response = werkzeug.wrappers.Response()
        response.mimetype = 'application/pdf'
        response.data = pickings.get_merged_ups_labels()

        return response
