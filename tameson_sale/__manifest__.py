# -*- coding: utf-8 -*-
{
    'name': 'Tameson Sale Customizations',
    'version': '13.0.0.1.0.0',
    'description': """
    Tameson Sale Customizations.

    Includes fields to enable invoice control policy (ordered/delivered)
    on sale order/sale order lines/payment terms (over-riding the product).
    Adds a field to mark the order as paid.
    Runs periodic checks to make sure the business logic is correct and
    a cron job to send notifications when it finds non-validated invoices
    for done pickings.

    """,
    'author': "Tameson",
    'depends': [
        'sale_stock',
        'tameson_account',
        'tameson_base',
        'tameson_product',
        'sale_crm',
        'delivery',
    ],
    'data': [
        'data/group.xml',
        'security/ir.model.access.csv',
        'data/cron.xml',
        'data/mail_data.xml',
        'views/sale_views.xml',
        'report/report_invoice.xml',
        'report/report_sale_order.xml',
        'report/report_external_layout.xml',
        'data/report_layout.xml',
        'wizard/base_document_layout_views.xml',
        'views/res_country_view.xml',
        'views/partner.xml',
        'wizard/product_creation.xml',
        'views/stock.xml'
    ],
    'application': False,
    'license': u'OPL-1',
}
