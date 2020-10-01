{
    'name': 'Channable Integration',
    'version': '13.0.0.1.0.0',
    'description': """
    Channable Integration.

    Includes the Channable API integration.
    Synchronization of orders between Odoo
    and Channable.

    """,
    'author': "Tameson",
    'depends': [
        'sale',
        'delivery',
        'celery',
    ],
    'data': [
        'data/ir_config_param_data.xml',
        'data/ir_cron_data.xml',
        'data/product_data.xml',
        'views/res_config_settings_views.xml',
        'views/res_company_view.xml',
        'views/account_journal_views.xml',
        'views/delivery_carrier_views.xml',
        'views/sale_order_views.xml',
        'views/menus.xml',
    ],
    'application': True,
    'license': u'OPL-1',
}
