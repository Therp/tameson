{
    'name': 'Prestashop Integration',
    'version': '13.0.0.1.0.0',
    'description': """
    Prestashop Integration.

    Pulls Orders from prestashop API
    Syncs orders status from Odoo to Prestashop

    """,
    'author': "Tameson",
    'depends': [
        'tameson_sale',
        'tameson_delivery_ups',
        'celery',
    ],
    'data': [
        'data/cron.xml',
        'security/ir.model.access.csv',
        'views/prestashop_config.xml',
        'views/delivery.xml',
        'views/sale.xml',
    ],
    'application': True,
    'external_dependencies': {
        'python': [
            'prestapyt'
        ],
    },

}
