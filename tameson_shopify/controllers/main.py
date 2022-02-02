# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo.http import route, request, Controller
from odoo.exceptions import UserError, ValidationError

from multipass import Multipass

class Shopify(Controller):

    @route(['/shopify_hosts'], type='http', auth="user", website=True)
    def shopify_hosts(self, **kw):
        instances = request.env['shopify.instance.ept'].sudo().search([('shopify_multipass_secret','!=',False)])
        return request.render("tameson_shopify.portal_shopify_hosts", {'instances': instances})

    @route(['/shopify_auth/<int:instance_id>'], type='http', auth="user", website=True)
    def shopify_auth(self, instance_id, **kw):
        instance = request.env['shopify.instance.ept'].sudo().browse(instance_id)
        partner = request.env.user.partner_id
        partner_data = partner._get_shopify_partner_data()
        multipass = Multipass(instance.shopify_multipass_secret)
        url = multipass.generateURL(partner_data, instance.shopify_host)
        return request.redirect(url)
