# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.http import request


class Http(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _dispatch(cls, endpoint):
        if "url" in request.params:
            request.session["shopify_page"] = request.params["url"]
        return super()._dispatch(endpoint)
