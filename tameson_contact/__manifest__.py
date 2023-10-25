{
    "name": "Tameson Contact Customizations",
    "version": "13.0.0.0.0.0",
    "description": """
    * Contact creation duplicate email constraint
      This will raise a validation error if contact with same email in system (not parent/child) exists.
    * Also, this adds permissions for sales_team.Administrator users to merge contacts.
    * This module will add the server action for admin/settings users to find and
      merge all contacts having duplicate emails. Child contacts will be archived
      if same zip code, will set as other address if different zip code, newest
      delivery and invoice contact will remain unchanged.
    """,
    "author": "Tameson",
    "depends": [
        "base_address_extended",
        "sales_team",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/contact.xml",
        "wizard/tameson_merge.xml",
        "views/partner_type.xml",
        "wizard/contact_creation.xml",
    ],
    "application": False,
}
