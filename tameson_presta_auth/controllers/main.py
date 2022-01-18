
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################
from odoo import SUPERUSER_ID
from odoo.http import route, request
from odoo.addons.web.controllers.main import Home
from addons.web.controllers.main import ensure_db

class PrestaAuth(Home):

    @route('/web/login', type='http', auth="none")
    def web_login(self, redirect=None, **kw):
        ensure_db()
        if request.httprequest.method == 'POST':
            presta_user = request.env['presta.users'].with_user(SUPERUSER_ID).search([('login','=',request.params['login'])], limit=1)
            if presta_user:
                presta_user._check_hash(request.params['password'])
        return super(PrestaAuth, self).web_login(redirect, **kw)