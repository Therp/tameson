# -*- coding: utf-8 -*-
{
    'name': 'Tameson Helpdesk Customizations',
    'version': '13.0.0.1.0.0',
    'description': """
    Tameson Helpdesk Customizations.
    """,
    'author': "Tameson",
    'depends': [
        'helpdesk_sale',
        'helpdesk_account',
        'helpdesk_stock',
        'tameson_base',
        'website',
    ],
    'data': [
        'views/helpdesk_views.xml',
        'views/rma.xml',
    ],
    'application': False,
    'license': u'OPL-1',
}
