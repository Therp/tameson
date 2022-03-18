{
    'name': 'Tameson price history',
    'summary': 'Tameson price history',
    'version': '1.0',

    'description': """
Tameson price history
==============================================
- Adds price history based on list_price and vendor price

    """,

    'author': 'Tameson',
    'maintainer': 'Tameson',
    'contributors': ['Tameson <arahman@tameson.com>'],

    'website': 'http://www.gitlab.com/TM_FULLNAME',

    'license': 'AGPL-3',
    'category': 'Uncategorized',

    'depends': [
        'product',
    ],
    'external_dependencies': {
        'python': [
        ],
    },
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'views/supplier_price_history.xml',
        'views/sale_price_history.xml',
    ],
    'demo': [
    ],
    'js': [
    ],
    'css': [
    ],
    'qweb': [
    ],
    'images': [
    ],
    'test': [
    ],

    'installable': True
}
