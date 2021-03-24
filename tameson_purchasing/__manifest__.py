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
    ],
    'data': [
        'views/purchase_views.xml',
        'views/assets.xml',
        'wizard/purchase_order_line_csv_import_views.xml',
        "data/mail_data.xml"
    ],
    'application': False,
    'license': u'OPL-1',
}
