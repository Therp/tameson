###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################
from addons.web.controllers.main import ensure_db

from odoo import SUPERUSER_ID
from odoo.http import request, route

from odoo.addons.website.controllers.main import Website


class PrestaAuth(Website):
    @route(website=True, auth="public", sitemap=False)
    def web_login(self, redirect=None, *args, **kw):
        ensure_db()
        if request.httprequest.method == "POST":
            presta_user = (
                request.env["presta.users"]
                .with_user(SUPERUSER_ID)
                .search([("login", "=", request.params["login"])], limit=1)
            )
            if presta_user:
                presta_user._check_hash(request.params["password"])
        return super(PrestaAuth, self).web_login(redirect=redirect, *args, **kw)
