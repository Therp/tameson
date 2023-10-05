{
    "name": "Tameson Account Customizations",
    "version": "13.0.0.1.0.0",
    "description": """
    Tameson Account Customizations.

    Includes the payment terms custom fields (Invoice delivered quantities).

    """,
    "author": "Tameson",
    "depends": ["account_followup"],
    "data": [
        "security/account_security.xml",
        "views/account_views.xml",
        "views/invoice_report.xml",
        "views/res_partner.xml",
    ],
    "application": False,
    "license": "OPL-1",
}
