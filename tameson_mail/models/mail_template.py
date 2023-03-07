from odoo import api, models


class IrMailServer(models.Model):
    _name = "ir.mail_server"
    _inherit = "ir.mail_server"

    def build_email(
        self,
        email_from,
        email_to,
        subject,
        body,
        email_cc=None,
        email_bcc=None,
        reply_to=False,
        attachments=None,
        message_id=None,
        references=None,
        object_id=False,
        subtype="plain",
        headers=None,
        body_alternative=None,
        subtype_alternative="plain",
    ):

        if object_id and "partner_id" in object_id:
            # use country-specific e-mail address
            country_specific_email_from = False
            if (
                object_id.partner_id
                and object_id.partner_id.lang
                and object_id.partner_id.lang
            ):
                lang = object_id.partner_id.lang
                company = self.env.user.company_id
                # with closing(odoo.sql_db.db_connect(dbname).cursor()) as cr:
                #     country_specific_email_from = translate(cr, name=False, source_type=ttype, lang=lang, source=src)
                country_specific_email_from = self.env["ir.translation"]._get_source(
                    name="email",
                    types="model",
                    lang=lang,
                    source=company.email,
                    res_id=company,
                )
            if country_specific_email_from:
                email_from = country_specific_email_from
        return super(IrMailServer, self).build_email(
            email_from,
            email_to,
            subject,
            body,
            email_cc=email_cc,
            email_bcc=email_bcc,
            reply_to=reply_to,
            attachments=attachments,
            message_id=message_id,
            references=references,
            object_id=object_id,
            subtype=subtype,
            headers=headers,
            body_alternative=body_alternative,
            subtype_alternative=subtype_alternative,
        )


class MailActivity(models.Model):
    _inherit = "mail.activity"

    @api.model
    def create(self, values):
        user_id = self.env["res.users"].browse(values["user_id"])
        res_model = self.env["ir.model"].browse(values["res_model_id"]).model
        res_id = self.env[res_model].browse(values["res_id"])
        res_id.sudo().message_subscribe(partner_ids=user_id.partner_id.ids)
        return super(MailActivity, self).create(values)
