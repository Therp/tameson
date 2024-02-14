{
    "name": "Tameson Frontend Customizations",
    "version": "16.0.0.0.0",
    "description": """
    Tameson Frontend Customizations

    Footer links
    Odoo Brand remove from footer
    """,
    "author": "Tameson",
    "depends": [
        "portal",
        "website_sale",
        "auth_signup",
        "payment_custom",
        "sale_stock",
        "sale",
        "payment_mollie_official",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/website_templates.xml",
        "views/website_views.xml",
        "views/shopify_views.xml",
        "views/shopify_templates.xml",
        "data/payment_provider_data.xml",
    ],
    "qweb": [],
    "application": False,
    "license": "OPL-1",
    "assets": {
        "web.assets_frontend": [
            "tameson_website/static/src/js/payment.js",
            "tameson_website/static/src/scss/tameson.scss",
            "payment_mollie_official/static/src/js/payment_form.js",
            "payment_mollie_official/static/src/js/qr_dialog.js",
        ],
    },
}
