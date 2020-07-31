{
    'name': 'Tameson UPS module adaptations',
    'version': '13.0.0.1.0.0',
    'description': """
    Tameson customizations of the UPS module.

    """,
    'author': "Tameson",
    'depends': [
        'delivery_ups',
    ],
    'data': [
        'data/delivery_carrier.xml',
        'views/delivery_ups_views.xml',
        'views/sale_views.xml',
        'views/stock_views.xml',
    ],
    'application': False,
    'license': u'OPL-1',
}
