{
    "name": "Tameson Helpdesk Customizations",
    "version": "16.0.1.0.0",
    "author": "Tameson",
    "depends": [
        "helpdesk_sale",
        "helpdesk_account",
        "helpdesk_stock",
        "tameson_base",
        "tameson_sale",
        #"tameson_stock",
        "web",
    ],
    "assets": {
        "web.assets_frontend": [
            "static/src/js/*",
        ]
    },
    "data": [
        "views/helpdesk_views.xml",
        "views/rma.xml",
        #"views/stock.xml",
    ],
    "application": False,
    "license": "OPL-1",
}
