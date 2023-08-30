###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import api, models, tools


class MailTemplate(models.Model):
    _inherit = "mail.template"

    @api.model
    def render_post_process(self, html):
        lang = self.env.context.get("lang", "")
        signature = self.env.user.company_id.signature_ids.filtered(
            lambda s: s.lang == lang
        )[:1]
        if not signature:
            signature = self.env.user.company_id.signature_ids[:1]
        if signature:
            signature_html = signature.signature % self.env.user.name
            html = tools.append_content_to_html(html, signature_html, plaintext=False)
        html = super().render_post_process(html)
        return html
