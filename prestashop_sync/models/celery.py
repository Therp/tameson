
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

STATE_FAILURE = 'FAILURE'


class CeleryTask(models.Model):
    _inherit = 'celery.task'

    # def write(self, vals):
    #     res = super(CeleryTask, self).write(vals)
    #     if vals.get('state', False) == STATE_FAILURE:
    #         NotificationGroup = self.env.ref('celery.group_celery_manager', False)
    #         msg = 'Model: %s Method: %s Task: %s failed.' % (self.model, self.method, self.uuid)
    #         self.message_notify(
    #             subject='Task failed %s %s' % (self.model, self.method),
    #             body=msg,
    #             partner_ids=NotificationGroup.users.mapped('partner_id').ids,
    #             record_name=self.display_name,
    #             email_layout_xmlid='mail.mail_notification_light',
    #             model_description='Celery Task',
    #         )
    #     return res
    
    def _states_to_cancel(self):
        return ['PENDING', 'SCHEDULED', 'STARTED']
