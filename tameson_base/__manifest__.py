# -*- coding: utf-8 -*-
{
    'name': 'Tameson Base Customizations',
    'version': '13.0.0.1.0.0',
    'description': """
    Tameson Base Customizations.

    Fields:
    - Model specific help text field.
    """,
    'author': "Tameson",
    'depends': [
        'base'
    ],
    'data': [
        'views/model.xml',
        'views/set_help.xml',
        'views/assets.xml',
    ],
    'application': False,
}
