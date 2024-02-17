###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

import base64

from odoo import _, fields, models
from odoo.exceptions import UserError


class MailTemplate(models.Model):
    _inherit = "mail.template"

    report_ids = fields.One2many(
        string="Multi Report",
        comodel_name="mail.template.multireport",
        inverse_name="template_id",
    )

    def generate_email(self, res_ids, fields):
        res = super().generate_email(res_ids, fields)
        multi_mode = True
        if isinstance(res_ids, int):
            res_ids = [res_ids]
            multi_mode = False
        records = self.env[self.model].browse(res_ids)
        for record in records:
            record_data = res[record.id] if multi_mode else res
            for multi_report in self.report_ids:
                attachments = record_data.get("attachments", [])
                report_name = multi_report.report_name
                report = multi_report.report_template
                res_id = record.id
                report_service = report.report_name
                if report.report_type in ["qweb-html", "qweb-pdf"]:
                    result, report_format = self.env[
                        "ir.actions.report"
                    ]._render_qweb_pdf(report, [res_id])
                else:
                    res = self.env["ir.actions.report"]._render(report, [res_id])
                    if not res:
                        raise UserError(
                            _("Unsupported report type %s found.", report.report_type)
                        )
                    result, report_format = res
                result = base64.b64encode(result)
                if not report_name:
                    report_name = "report." + report_service
                ext = "." + report_format
                if not report_name.endswith(ext):
                    report_name += ext
                attachments.append((report_name, result))
                record_data["attachments"] = attachments
        return res


class TemplateMultiReport(models.Model):
    _name = "mail.template.multireport"
    _description = "Multiple Report"

    _rec_name = "report_template"
    _order = "report_template ASC"

    report_name = fields.Char(
        "Report Filename", translate=True, prefetch=True, required=True
    )
    report_template = fields.Many2one("ir.actions.report", required=True)
    template_id = fields.Many2one("mail.template", required=True)
