import logging
from email.utils import COMMASPACE

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    notification_email = fields.Char("Notification Email")


class IrMailServer(models.Model):
    _inherit = "ir.mail_server"

    @api.model
    def send_email(self, message, *args, **kwargs):
        do_not_send_copy = self.env.context.get("do_not_send_copy", False)
        notification_email = self.env.user.company_id.notification_email
        if not do_not_send_copy:
            if message["Bcc"]:
                message["Bcc"] = message["Bcc"].join(COMMASPACE, notification_email)
            else:
                message["Bcc"] = notification_email
        return super().send_email(message, *args, **kwargs)
