{
    "name": "Tameson Frontend Customizations",
    "version": "13.0.0.0.0",
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
    ],
    "data": [
        "views/website_templates.xml",
        "views/website_views.xml",
        "views/shopify_views.xml",
        "views/shopify_templates.xml",
    ],
    "qweb": [],
    "application": False,
    "license": "OPL-1",
    "assets": {
        "web.assets_frontend": ["tameson_website/static/src/js/payment.js"],
    },
}
