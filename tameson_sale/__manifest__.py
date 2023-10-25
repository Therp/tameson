{
    "name": "Tameson Sale Customizations",
    "version": "13.0.0.1.0.0",
    "description": """
    Tameson Sale Customizations.
    """,
    "author": "Tameson",
    "depends": ["sale", "tameson_product", "delivery"],
    "data": [
        # "data/group.xml",
        "security/ir.model.access.csv",
        # "data/cron.xml",
        # "data/mail_data.xml",
        "wizard/reshipment.xml",
        "views/sale_views.xml",
        # "report/report_invoice.xml",
        # "report/report_sale_order.xml",
        "report/report_external_layout.xml",
        # "data/report_layout.xml",
        # "wizard/base_document_layout_views.xml",
        # "views/res_country_view.xml",
        # "views/partner.xml",
        "wizard/product_creation.xml",
        # "views/stock.xml",
        "views/pricelist.xml",
    ],
    "application": False,
    "license": "OPL-1",
}
