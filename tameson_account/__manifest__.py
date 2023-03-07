{
    "name": "Tameson Account Customizations",
    "version": "13.0.0.1.0.0",
    "description": """
    Tameson Account Customizations.

    Includes the payment terms custom fields (Invoice delivered quantities).

    """,
    "author": "Tameson",
    "depends": [
        "tameson_base",
        "account_intrastat",  # enterprise
        "l10n_nl_intrastat",  # enterprise, with 'account.move.line.intrastat_product_origin_country_id field'
        "payment_adyen",
        "account_bank_statement_import_online_paypal",  # online paypal import for interval change
    ],
    "data": [
        "security/account_security.xml",
        "views/account_views.xml",
        "views/invoice_report.xml",
        "views/res_partner.xml",
    ],
    "application": False,
    "license": "OPL-1",
}
