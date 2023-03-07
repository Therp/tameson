from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    phone = fields.Char(translate=True)
    email = fields.Char(translate=True)
    website = fields.Char(translate=True)
    report_header2 = fields.Text(
        string="Report Header (2)",
        translate=True,
        help="Appears by default on the top right corner of your printed documents (report header).",
    )
    report_header3 = fields.Text(
        string="Report Header (3)",
        translate=True,
        help="Appears by default on the top right corner of your printed documents (report header).",
    )


class ResPartner(models.Model):
    _inherit = "res.partner"

    phone = fields.Char(translate=True)
    email = fields.Char(translate=True)
    website = fields.Char(translate=True)
