# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo.http import request, route
from odoo import tools, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.base_vat.models.res_partner import _region_specific_vat_codes, _ref_vat


class CustomerPortal(CustomerPortal):
    def details_form_validate(self, data):
        error, error_message = super(CustomerPortal, self).details_form_validate(data)
        partner = request.env.user.partner_id
        if error.get("vat", False) == "error":
            country = (int(data['country_id']) if data.get('country_id') else False)
            country = request.env['res.country'].browse(country).code.lower()
            if not country:
                country = partner.country_id
            vat_country_code = country.code.lower()
            _ref_vat_no = "'CC##' (CC=Country Code, ##=VAT Number)"
            _ref_vat_no = _ref_vat.get(vat_country_code) or _ref_vat_no
            error_message.append(_('The VAT number either failed the VIES VAT validation check or did not respect the expected format ') + _ref_vat_no)
        return error, error_message

    @route(['/my/address/<int:child_pos>'], type='http', auth='user', website=True)
    def address(self, child_pos, redirect=None, **post):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id.child_ids[child_pos]
        values.update({
            'error': {},
            'error_message': [],
        })

        if post and request.httprequest.method == 'POST':
            error, error_message = self.details_form_validate(post)
            values.update({'error': error, 'error_message': error_message})
            values.update(post)
            if not error:
                values = {key: post[key] for key in self.MANDATORY_BILLING_FIELDS}
                values.update({key: post[key] for key in self.OPTIONAL_BILLING_FIELDS if key in post})
                for field in set(['country_id', 'state_id']) & set(values.keys()):
                    try:
                        values[field] = int(values[field])
                    except:
                        values[field] = False
                values.update({'zip': values.pop('zipcode', '')})
                partner.sudo().write(values)
                if redirect:
                    return request.redirect(redirect)
                return request.redirect('/my/home')

        countries = request.env['res.country'].sudo().search([])
        states = request.env['res.country.state'].sudo().search([])

        values.update({
            'form': '/my/address/%d' % child_pos,
            'partner': partner,
            'countries': countries,
            'states': states,
            'has_check_vat': hasattr(request.env['res.partner'], 'check_vat'),
            'redirect': redirect,
            'page_name': 'my_details',
        })

        response = request.render("tameson_website.portal_address", values)
        response.headers['X-Frame-Options'] = 'DENY'
        return response
