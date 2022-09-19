# Copyright 2020 Therp BV <https://therp.nl>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "Procurement purchase no grouping for Tameson",
    "version": "13.0.1.0.0",
    "author": "Therp BV",
    "license": "AGPL-3",
    "category": "purchase",
    "depends": [
        "sale",
        "procurement_purchase_no_grouping",
        "purchase_stock",
        "sale_stock",
        "tameson_stock",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/purchase_order.xml",
        "views/res_partner.xml",
        "views/stock_picking.xml",
        "views/reports.xml",
        "report/stock_report_views.xml",
        "security/security.xml",
    ],
    "installable": True,
}
