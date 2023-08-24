###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import api, models, tools


class MailTemplate(models.Model):
    _inherit = "mail.template"

    @api.model
    def render_post_process(self, html):
        lang = self.env.context.get("lang")
        signature = self.env.user.with_context(lang=lang).signature
        html = tools.append_content_to_html(html, signature, plaintext=False)
        html = super().render_post_process(html)
        return html
