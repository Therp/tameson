# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo.http import request
from odoo import tools, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.base_vat.models.res_partner import _region_specific_vat_codes


class CustomerPortal(CustomerPortal):
    def details_form_validate(self, data):
        error, error_message = super(CustomerPortal, self).details_form_validate(data)
        partner = request.env.user.partner_id
        if error.get("vat", False) == "error":
            vat_country_code, vat_number = partner._split_vat(data['vat'])
            if not partner.simple_vat_check(vat_country_code, vat_number):
                message = "Invalid VAT format."
            else:
                # quick and partial off-line checksum validation
                message = "VIES VAT verification failed."
            error_message.append(_(message))
        return error, error_message
