
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

import logging
_logger = logging.getLogger(__name__)


class TamesonMergeContact(models.TransientModel):
    _name = 'tameson.merge.contact'
    _description = 'Tameson Merge Contact'
    
    line_ids = fields.One2many(comodel_name='tameson.merge.contact.line', inverse_name='merge_id',)
    
    @api.model
    def default_get(self, fields):
        res = super(TamesonMergeContact, self).default_get(fields)
        self.env.cr.execute("""
select ids, email
    from (
        select array_agg(id) ids, count(id), email
            from res_partner
            where parent_id is null and
            email is not null
            group by email) as subquery
        where count > 1
union
select ARRAY[parent.id] id, rp.email 
    from (
        select parent_id id, count(parent_id) 
            from res_partner 
                where active = True 
                group by parent_id) parent 
            left join res_partner rp 
                on parent.id = rp.id 
            where parent.count > 2;
""")
        pidss = self.env.cr.fetchall()
        lines  = [(0, 0, {'partner_ids': [(6, 0, ids)], 'partner_email': email})for ids, email in pidss]
        res.update({
            'line_ids': lines
        })
        return res

    def action_merge(self):
        for line in self.line_ids:
            ids = line.partner_ids.ids
            if len(ids) > 1:
                wiz = self.env['base.partner.merge.automatic.wizard'].with_context(active_ids=ids,active_model='res.partner').create({})
                wiz.write({'dst_partner_id': max(ids)})
                partner = wiz.dst_partner_id
                wiz.with_context(skip_email_check=True).action_merge()
            elif len(ids) == 1:
                partner = line.partner_ids
            else:
                return
            del_inv = self.env['res.partner']
            other = self.env['res.partner']
            arch = self.env['res.partner']
            del_inv += partner.child_ids.filtered(lambda p: p.type == 'delivery').sorted('id', reverse=True)[:1]
            del_inv += partner.child_ids.filtered(lambda p: p.type == 'invoice').sorted('id', reverse=True)[:1]
            for child in partner.child_ids - del_inv:
                if (child.zip or "").lower().strip() not in (del_inv + other).mapped(lambda p: (p.zip or "").lower().strip()):
                    other += child
                else:
                    arch += child
            _logger.warning("Archive: %d Other: %d" % (len(arch), len(other)))
            arch.action_archive()
            other.write({'type': 'other'})

class TamesonMergeContactLine(models.TransientModel):
    _name = 'tameson.merge.contact.line'
    _description = 'Tameson Merge Contact'

    merge_id = fields.Many2one(comodel_name='tameson.merge.contact',ondelete='cascade',)
    
    partner_ids = fields.Many2many(comodel_name='res.partner')
    partner_email = fields.Char()    
    

