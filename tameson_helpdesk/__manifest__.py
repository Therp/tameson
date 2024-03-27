{
    "name": "Tameson Helpdesk Customizations",
    "version": "16.0.1.0.0",
    "author": "Tameson",
    "depends": [
        "helpdesk_account",
        "helpdesk_sale",
        "helpdesk_stock",
        "tameson_base",
        "tameson_sale",
        "web",
    ],
    "assets": {
        "web.assets_frontend": [
            "tameson_helpdesk/static/src/js/*",
        ]
    },
    "data": [
        "views/helpdesk_views.xml",
        "views/rma.xml",
    ],
    "application": False,
    "license": "OPL-1",
}
