# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint
from odoo import SUPERUSER_ID
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
        if not order:
            # from /payment/pay links, sale order is not found from website session
            # get order from trasnaction reference
            order = request.env["payment.transaction"].sudo().search(
                [("reference", "=", post.get("reference"))]
            ).sale_order_ids[:1].sudo()
        request.env["payment.transaction"].sudo()._handle_notification_data(
            "custom", post
        )
        wp_id = order.payment_term_id.workflow_process_id
        order.sudo().write(
            {
                "require_signature": True,
                "require_payment": False,
                "workflow_process_id": wp_id.id,
            }
        )
        order.with_user(order.user_id or SUPERUSER_ID).with_delay(
            eta=60 * 60 * 6
        ).action_send_signature_remaining()
        return request.redirect(order.get_portal_url())
