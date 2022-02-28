
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class PickingDelay(models.TransientModel):
    _name = 'picking.delay.mail'
    _inherits = {'mail.compose.message':'composer_id'}

    composer_id = fields.Many2one('mail.compose.message', string='Composer', required=True, ondelete='cascade')
    template_id = fields.Many2one('mail.template', 'Use template', index=True, domain="[('model', '=', 'stock.picking')]")
    picking_ids = fields.Many2many('stock.picking', 'delay_mail_picking_rel', string='Pickings')

    @api.model
    def default_get(self, fields):
        picking_ids = (
            self.env["stock.picking"]
            .search(
                [
                    ("activity_exception_decoration", "!=", False),
                    ("state", "in", ("waiting", "confirmed")),
                    ("picking_type_code", "=", "outgoing"),
                ]
            )
            .filtered(
                lambda p: p.activity_ids.filtered(
                    lambda a: "The scheduled date" in a.note
                )
            )
        )
        res = super(PickingDelay, self).default_get(fields)
        template = self.env.ref('tameson_stock.tameson_picking_order_delay').id
        if not template:
            self.env['mail.template'].search([('model_id.model','=','stock.picking')], limit=1).id
        composer_id = self.env['mail.compose.message'].create({
            'composition_mode': 'mass_mail',
            'use_active_domain': False,
        }).id
        res.update({
            'template_id': template,
            'picking_ids': picking_ids.ids,
            'composer_id': composer_id,
            'model': 'stock.picking',
        })
        return res

    def send(self):
        self.composer_id.template_id = self.template_id.id
        self.composer_id.onchange_template_id_wrapper()
        self.composer_id.with_context(active_ids=self.picking_ids.ids).send_mail()
        self.picking_ids.mapped('activity_ids').filtered(lambda a: 'The scheduled date' in a.note)\
            .action_feedback(feedback='Delay mail sent.')
