# Custom Exports module
{
    "name": "Custom SFTP Exports",
    "version": "16.0.1.0.0",
    "summary": "Custom Exports via SFTP",
    "sequence": 10,
    "category": "General",
    "author": "Tameson",
    "license": "Other proprietary",
    "depends": ["base", "product"],
    "external_dependencies": {
        "python": ["paramiko"],
    },
    "data": [
        "security/ir.model.access.csv",
        "views/custom_exporter_view.xml",
        "views/sftp_server_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
