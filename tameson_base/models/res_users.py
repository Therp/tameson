###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import api, fields, models


@api.model
def _lang_get(self):
    return self.env["res.lang"].get_installed()


class ResCompany(models.Model):
    _inherit = "res.company"

    signature_ids = fields.One2many(
        comodel_name="signature.lang",
        inverse_name="company_id",
    )


class SignatureLang(models.Model):
    _name = "signature.lang"
    _description = "SignatureLang"

    _rec_name = "lang"
    _order = "sequence ASC"

    company_id = fields.Many2one(
        comodel_name="res.company",
        ondelete="restrict",
    )
    sequence = fields.Integer(string="Line Number", default=10)
    lang = fields.Selection(
        _lang_get,
        string="Language",
        default=lambda self: self.env.lang,
        help="All the emails and documents sent to this contact will be translated in this language.",
    )
    signature = fields.Html()
