# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from odoo.addons.delivery_ups_rest.models.ups_request import UPSRequest

original_set_package_details = UPSRequest._set_package_details


def new_set_package_details(
    self, packages, carrier, ship_from, ship_to, cod_info, ship=False, is_return=False
):
    res_packages = original_set_package_details(
        self, packages, carrier, ship_from, ship_to, cod_info, ship, is_return
    )
    for package in res_packages:
        if not package.get("Description") and ship_to.country_id.code == "MX":
            package["Description"] = "Fluid control components"
    return res_packages


UPSRequest._set_package_details = new_set_package_details
