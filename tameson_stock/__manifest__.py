{
    "name": "Tameson Stock Customizations",
    "version": "13.0.0.1.0.0",
    "description": """
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

    Adds action `Send delay mail` on stock.picking list view, can be used to
    send Delivery delayed mail to all delayed delivery partners.
    Pickings auto selected if Delivery, waiting, have exception containing
    'The scheduled date' string.
    """,
    "author": "Tameson",
    "depends": [
        "sale_stock",
        "stock_account",
        "stock_picking_batch",
        "tameson_sale",
        "tameson_product",
        "tameson_base",
        "delivery",
        "sale_sourced_by_line",
        "stock_mts_mto_rule",
        "purchase_stock",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/params.xml",
        "data/cron.xml",
        "data/cron_min_qty.xml",
        "data/migrations.xml",
        "report/picking_batch.xml",
        "report/stock.xml",
        "report/report_deliveryslip.xml",
        "report/report_stockpicking_operations.xml",
        "views/stock_picking_views.xml",
        "views/stock_warehouse_orderpoint_views.xml",
        "views/product_views.xml",
        "views/sale_views.xml",
        "views/templates.xml",
        "data/mail_data.xml",
        "wizards/delay_mail.xml",
        "views/aa_views.xml",
    ],
    "qweb": [
        "static/src/xml/qweb.xml",
        "static/src/xml/qty_at_date.xml",
    ],
    "application": False,
    "license": "OPL-1",
}
