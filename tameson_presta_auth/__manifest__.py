# -*- coding: utf-8 -*-
{
    'name': 'Tameson Prestashop Authentication',
    'version': '13.0.0.1.0.0',
    'description': """
Tameson Prestashop Authentication
=======================================
Tries to authenticate credentials against prestashop hashing method
If successful converts customer (matched by email) into portal user,
Sets same password for that portal user.

    """,
    'author': "Tameson",
    'depends': [
        'base',
        'portal'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/presta_users.xml',
    ],
    'application': False,
}
