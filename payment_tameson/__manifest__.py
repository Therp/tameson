# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "Payment Tameson",
    "version": "2.0",
    "category": "Accounting/Payment Providers",
    "sequence": 350,
    "summary": "A payment provider for custom flows like wire transfers.",
    "depends": ["payment_custom"],
    "data": [
        "data/payment_provider_data.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            # 'payment_custom/static/src/js/post_processing.js',
        ],
    },
    "application": False,
    "license": "LGPL-3",
}
