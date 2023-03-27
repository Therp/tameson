{
    "name": "Tameson Stock Customizations",
    "version": "13.0.0.1.0.0",
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
