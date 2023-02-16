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
        'tameson_sale',
        'queue_job',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_level.xml',
        'views/sale.xml',
        'views/templates.xml',
        'views/shopify.xml',
        'data/job_channel_data.xml',
    ],
    'application': False,
}
