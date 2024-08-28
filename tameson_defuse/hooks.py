import os


ANONYMIZATION_QUERIES = [
    ""
    "UPDATE account_move SET ref = ",
    "UPDATE account_move_line SET amount_currency = 0.0",
    "UPDATE account_move_line SET debit = 0.0",
    "UPDATE account_move_line SET credit = 0.0",
    "UPDATE account_move_line SET name = 'anonymized' || id",
    "UPDATE account_move_line SET price_unit = 0.0",
    "UPDATE product_template SET list_price = 0.0",
    "UPDATE product_template SET sale_price_usd = 0.0",
    "UPDATE product_template SET sale_price_gbp = 0.0",
    "UPDATE purchase_order_line SET price_unit = 0.0",
    "UPDATE purchase_order_line SET price_subtotal = 0.0",
    "UPDATE purchase_order_line SET price_total = 0.0",
]

ANONYMIZATION_INFO = {
    "account_asset": {
        "book_value": "0.0",
        "original_value": "0.0",
        "value_residual": "0.0",
    },
    "account_bank_statement": {
        "difference": "0.0",
    },
    "account_bank_statement_line": {
        "amount": "0.0",
    },
    "account_bank_statement_line": {
        "amount_currency": "0.0",
    },
    "account_move": {
        "amount_residual": "0.0",
        "amount_residual_signed": "0.0",
        "amount_tax": "0.0",
        "amount_tax_signed": "0.0",
        "amount_total": "0.0",
        "amount_total_in_currency_signed": "0.0",
        "amount_total_signed": "0.0",
        "amount_untaxed": "0.0",
        "amount_untaxed_signed": "0.0",
        "asset_depreciated_value": "0.0",
        "asset_remaining_value": "0.0",
        "ref": "'anonymized' || id",
    },
    "account_move_line": {
        "amount_currency": "0.0",
        "amount_residual": "0.0",
        "amount_residual_currency": "0.0",
        "balance": "0.0",
        "credit": "0.0",
        "debit": "0.0",
        "discount": "0.0",
        "line_tax_amonut_percent": "0.0",
        "name": "'anonymized' || id",
        "price_unit": "0.0",
        "price_subtotal": "0.0",
        "price_total": "0.0",
        "quantity": "0.0",
        "tax_base_amount": "0.0",
    },
    "account_partial_reconcile": {
        "amount": "0.0",
        "credit_amount_currency": "0.0",
        "debit_amount_currency": "0.0",
    },
    "account_payment": {
        "amount": "0.0",
        "amount_company_currency_signed": "0.0",
    },
    "purchase_order": {
        "amount_total": "0.0",
        "amount_tax": "0.0",
        "amount_untaxed": "0.0",
    },
    "purchase_order_line": {
        "price_unit": "0.0",
        "price_subtotal": "0.0",
        "price_total": "0.0",
    },
    "product_template": {
        "list_price": "0.0",
        "sale_price_usd": "0.0",
        "sale_price_gbp": "0.0",
    },
}


def anonymize_database(cr):
    for table_name, fields in ANONYMIZATION_INFO.items():
        for field_name, value in fields.items():
            cr.execute("UPDATE \"%s\" SET \"%s\" = %s" % [table_name, field_name, value])

def check_if_defused(cr):
    cr.execute("SELECT value FROM ir_config_parameter WHERE key = 'tameson_defuse.is_defused'")
    res = cr.dictfetchone()
    if res:
        return res["value"].lower() in ["1", "true", "yes"]
    return False

def defuse_database(cr):
    if not check_if_defused(cr):
        return

    queries = [
        "UPDATE delivery_carrier SET active = FALSE WHERE name::text LIKE '%UPS%'",
        "UPDATE shopify_instance_ept SET active = FALSE",
        #"DELETE FROM account_online_link",
        # Anonymization queries
        "UPDATE account_move SET partner_id = 2 WHERE move_type = 'in_invoice'",
    ]
    for query in queries:
        cr.execute(query)

    anonymize_database(cr)
    mark_defused(cr)

def mark_defused(cr, defused):
    cr.execute("""
        INSERT INTO ir_config_parameter (key, value)
        VALUES ('tameson_defuse.is_defused', '1')
        ON CONFLICT(key) DO UPDATE SET value = '1'
    """)

def on_post_init(cr):
    stage = os.environ.get("ODOO_STAGE")
    if stage != "production":
        defuse_database(cr)
