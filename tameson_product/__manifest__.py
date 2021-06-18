# -*- coding: utf-8 -*-
{
    'name': 'Tameson Product Customizations',
    'version': '13.0.0.1.0.0',
    'description': """
    Tameson Product Customizations.
    
    Includes additional Tameson specific fields added to products
    (Pimcore specific and other usage).

    Also includes the computed stored fields for vendor name,
    vendor SKU and vendor delivery lead time
    (first vendor only if multiple are found).

    """,
    'author': "Tameson",
    'depends': [
        'product',
        'tameson_base',
    ],
    'data': [
        'views/product_views.xml',
    ],
    'application': False,
    'license': u'OPL-1',
}
