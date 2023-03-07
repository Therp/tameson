from odoo import api, fields, models


class BaseDocumentLayout(models.TransientModel):
    _inherit = "base.document.layout"

    report_header2 = fields.Text(related="company_id.report_header2", readonly=False)
    report_header3 = fields.Text(related="company_id.report_header3", readonly=False)

    @api.onchange("company_id")
    def _onchange_company_id(self):
        res = super(BaseDocumentLayout, self)._onchange_company_id()
        for wizard in self:
            wizard.report_header2 = wizard.company_id.report_header2
            wizard.report_header3 = wizard.company_id.report_header3
        return res
