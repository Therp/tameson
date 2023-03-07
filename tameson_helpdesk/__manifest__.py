{
    "name": "Tameson Helpdesk Customizations",
    "version": "13.0.0.1.0.0",
    "description": """
    Tameson Helpdesk Customizations.
    """,
    "author": "Tameson",
    "depends": [
        "helpdesk_sale",
        "helpdesk_account",
        "helpdesk_stock",
        "tameson_base",
        "tameson_sale",
        "website",
    ],
    "data": [
        "views/helpdesk_views.xml",
        "views/rma.xml",
        "views/stock.xml",
    ],
    "application": False,
    "license": "OPL-1",
}
