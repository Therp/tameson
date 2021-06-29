# -*- coding: utf-8 -*-
{
    'name': 'Tameson Contact Customizations',
    'version': '13.0.0.0.0.0',
    'description': """
    * Contact creation duplicate email constraint
    This will raise a validation error if contact with same email in system (not parent/child) exists.

    Also, this adds permissions for sales_team.Administrator users to merge
    contacts.
    """,
    'author': "Tameson",
    'depends': [
        'base_address_extended',
        'sales_team',
    ],
    'data': [
        'views/contact.xml',
        'wizard/tameson_merge.xml',
    ],
    'application': False,
}
