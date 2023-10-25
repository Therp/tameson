{
    "name": "Tameson Base Customizations",
    "version": "13.0.0.1.0.0",
    "description": """
    Tameson Base Customizations.
    * Week of year set on ISO standard (4 day in January rule)

    Fields:
    - Model specific help text field.
    """,
    "author": "Tameson",
    "depends": [
        "mail",
    ],
    "data": [
        "security/groups.xml",
        "views/model.xml",
        "views/set_help.xml",
        "views/aa_comm.xml",
        "security/ir.model.access.csv",
    ],
    "application": False,
}
