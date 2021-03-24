# -*- coding: utf-8 -*-
{
    'name': 'Tameson Stock Customizations',
    'version': '13.0.0.1.0.0',
    'description': """
    Tameson Stock Customizations.

    Adds inventory specific custom fields to pickings:
    delivery allowed, out of EU and fully paid flags,
    as well as automated invoicing features,
    reordering rules adjustments, additional reports
    and UPS labels controller.

    This module also adds 2 new fields to products:
    Minimal QTY Available and Minimal QTY Available Date.
    They inform a user of the minimal quantity of a product based on
    future stock moves as well as the date when this will occur.
    Also visible on the sales order line displaying a warning
    when the ordered quantity goes above it.

    Also, cron job is added to perform automatic change to 'buy' route for
    products with an orderpoint and 'buy' + 'mto+mts' for products which are not
    in an orderpoint.

    """,
    'author': "Tameson",
    'depends': [
        'sale_stock',
        'stock_account',
        'stock_picking_batch',
        'tameson_sale',
        'tameson_product',
    ],
    'data': [
        'data/params.xml',
        'data/automated_actions.xml',
        'data/cron.xml',
        'data/cron_min_qty.xml',
        'data/migrations.xml',
        'report/picking_batch.xml',
        'report/stock.xml',
        'report/report_deliveryslip.xml',
        'report/report_stockpicking_operations.xml',
        'views/stock_picking_views.xml',
        'views/stock_warehouse_orderpoint_views.xml',
        'views/product_views.xml',
        'views/sale_views.xml',
        'views/templates.xml',
        'data/mail_data.xml'
    ],
    'qweb': [
        'static/src/xml/qweb.xml',
        'static/src/xml/qty_at_date.xml',
    ],
    'application': False,
    'license': u'OPL-1',
}
