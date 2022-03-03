{
    'name': 'Tameson Frontend Customizations',
    'version': '13.0.0.0.0',
    'description': """
    Tameson Frontend Customizations

    Footer links
    Odoo Brand remove from footer
    """,
    'author': "Tameson",
    'depends': [
        'portal',
        'website',
    ],
    'data': [
        'views/website.xml',
    ],
    'qweb': [
        'static/src/xml/qweb.xml',
        'static/src/xml/qty_at_date.xml',
    ],
    'application': False,
    'license': u'OPL-1',
}
