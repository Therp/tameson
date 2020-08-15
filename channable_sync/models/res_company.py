import requests
from odoo import api, fields, models, _
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)


class ChannableAuth(requests.auth.AuthBase):
    def __init__(self, token):
        self.token = token

    def __call__(self, r):
        r.headers["authorization"] = "Bearer %s" % self.token
        return r


class ResCompany(models.Model):
    _inherit = 'res.company'

    channable_api_token = fields.Char(string="Channable API Token")
    channable_company_id = fields.Char(string="Channable Company ID")
    channable_project_id = fields.Char(string="Channable Project ID")
    channable_orders_shipped = fields.Boolean(string="Channable Order - Fetch Shipped", default=True)
    channable_orders_not_shipped = fields.Boolean(string="Channable Order - Fetch Not Shipped", default=True)
    channable_orders_cancelled = fields.Boolean(string="Channable Order - Fetch Cancelled", default=True)
    channable_orders_waiting = fields.Boolean(string="Channable Order - Fetch Waiting", default=True)

    def channable_request(self, method, endpoint, payload, headers={}, timeout=120):
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('channable_api_base_url', default='')
        if not base_url:
            raise UserError(_('Channable API base URL not set!'))

        channable_company_id = self.channable_company_id
        if not channable_company_id:
            raise UserError(_('Channable API Request Failed - Company ID not set!'))
        channable_project_id = self.channable_project_id
        if not channable_project_id:
            raise UserError(_('Channable API Request Failed - Project ID not set!'))

        request_url = '{base_url}/v1/companies/{company_id}/projects/{project_id}{endpoint}'.format(base_url=base_url,
                                                                                                    company_id=channable_company_id,
                                                                                                    project_id=channable_project_id,
                                                                                                    endpoint=endpoint)

        api_token = self.channable_api_token
        if not api_token:
            raise UserError(_('Channable API Authentification Failed - Unable to retrieve token!'))

        request_headers, request_params, request_data = {}, {}, {}
        if method == "POST":
            request_headers = {'Content-Type': 'application/json'}
            request_data = payload
        else:
            request_params = payload
        request_headers.update(headers)
        response = requests.request(method=method,
                                    url=request_url,
                                    auth=ChannableAuth(api_token),
                                    params=request_params,
                                    data=request_data,
                                    headers=request_headers,
                                    timeout=timeout)

        result = {}
        try:
            response.raise_for_status()
            result = response.json()
        except Exception as e:
            raise Warning(_('Channable API - invalid response! %s' % str(e)))

        return result
