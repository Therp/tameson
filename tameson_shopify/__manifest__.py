# -*- coding: utf-8 -*-
{
    'name': 'Tameson Shopify Customizations',
    'version': '13.0.0.1.0.0',
    'description': """
    Tameson Shopify Customizations.
    """,
    'author': "Tameson",
    'depends': [
        'shopify_ept',
        'tameson_contact',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_level.xml',
        'views/sale.xml'
    ],
    'application': False,
}
