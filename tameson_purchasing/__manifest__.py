# -*- coding: utf-8 -*-
{
    'name': 'Tameson Purchase customizations',
    'version': '13.0.0.1.0.0',
    'description': """
    Tameson Purchase Customizations.

    Includes fields to enable bill control policy (ordered/delivered)
    on purchase order and purchase order lines (over-riding the product).
    Adds a button on the PO to copy the contents of the order lines
    (quantity and vendor SKU) to the clipboard.

    """,
    'author': "Tameson",
    'depends': [
        'purchase_stock',
        'tameson_account',
        'tameson_base',
        'tameson_purchase'
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/purchase_views.xml',
        'wizard/purchase_order_line_csv_import_views.xml',
        "data/mail_data.xml",
        'views/stock.xml',
        'views/reports.xml',
    ],
    'application': False,
    'license': u'OPL-1',
}
