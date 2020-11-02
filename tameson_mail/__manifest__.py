{
    'name': 'Tameson Mailing Customizations',
    'version': '13.0.0.1.0.0',
    'description': """
    Tameson Mailing Customizations.

    Includes Tameson specific modifications of the e-mail
    templates and a custom logic to set the from address
    according to the partner country.

    """,
    'author': "Tameson",
    'depends': [
        'mail',
        'account',
        'tameson_sale',
    ],
    'data': [
        'data/mail_template_data.xml',
        'data/template.xml',
        'views/account_invoice_send_views.xml',
    ],
    'application': False,
    'license': u'OPL-1',
}
