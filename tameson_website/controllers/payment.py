# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint

from odoo.http import Controller, request, route

_logger = logging.getLogger(__name__)


class CustomController(Controller):
    _process_url = "/payment/custom/tameson_process"

    @route(
        _process_url,
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        website=True,
    )
    def custom_process_transaction(self, **post):
        _logger.info("Handling custom processing with data:\n%s", pprint.pformat(post))
        order = request.website.sale_get_order()
        request.env["payment.transaction"].sudo()._handle_notification_data(
            "custom", post
        )
        order.sudo().write(
            {
                "require_signature": True,
                "require_payment": False,
            }
        )
        return request.redirect(order.get_portal_url())
