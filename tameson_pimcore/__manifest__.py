{
    "name": "Tameson PIMCore Integration",
    "summary": "Tameson PIMCore Integration",
    "version": "13.0.0.0",
    "description": """
Tameson PIMCore Integration
==============================================
    * Syncs Product data from pimcore to odoo
    """,
    "author": "TM_FULLNAME",
    "maintainer": "TM_FULLNAME",
    "contributors": ["TM_FULLNAME <TM_FULLNAME@gmail.com>"],
    "website": "http://www.gitlab.com/TM_FULLNAME",
    "license": "AGPL-3",
    "category": "Uncategorized",
    "depends": [
        "product",
        "mail",
        "tameson_product",
        "mrp",
        "website_sale",
        "tameson_sale",
    ],
    "external_dependencies": {
        "python": ["aiohttp==3.7.4.post0", "gql==3.0.0a6"],
    },
    "data": [
        "security/groups.xml",
        "views/pimcore_config.xml",
        "views/pimcore_response.xml",
        "security/ir.model.access.csv",
        "data/cron.xml",
        "data/data.xml",
    ],
    "installable": True,
}
