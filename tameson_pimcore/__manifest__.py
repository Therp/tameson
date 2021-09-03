{
    'name': 'Tameson PIMCore Integration',
    'summary': 'Tameson PIMCore Integration',
    'version': '13.0.0.0',

    'description': """
Tameson PIMCore Integration
==============================================


    """,

    'author': 'TM_FULLNAME',
    'maintainer': 'TM_FULLNAME',
    'contributors': ['TM_FULLNAME <TM_FULLNAME@gmail.com>'],

    'website': 'http://www.gitlab.com/TM_FULLNAME',

    'license': 'AGPL-3',
    'category': 'Uncategorized',

    'depends': [
        'mail',
        'tameson_product',
        'mrp'
    ],
    'external_dependencies': {
        'python': [
        ],
    },
    'data': [
        'views/pimcore_config.xml',
        'views/pimcore_response.xml',
        'security/ir.model.access.csv',
        'data/cron.xml',
        'data/data.xml',
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
