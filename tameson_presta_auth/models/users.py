
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _, SUPERUSER_ID
from odoo.exceptions import UserError, ValidationError, AccessDenied
import bcrypt, hashlib

salt = '8kSCkZeFekwd0tX4A2FMAIqq6mnBKWpRFjJH6iT0K5arcjUfHBZWTBtK'

class ResUsers(models.Model):
    _inherit = 'res.users'

    # @classmethod
    # def _login(cls, db, login, password):
    #     try:
    #         return super(ResUsers, cls)._login(db, login, password)
    #     except AccessDenied:
    #         with cls.pool.cursor() as cr:
    #             env = api.Environment(cr, SUPERUSER_ID, {})
    #             UserModel = env[cls._name]
    #             user = UserModel.search(UserModel._get_login_domain(login), order=UserModel._get_login_order(), limit=1)
    #             if user:
    #                 raise AccessDenied()
    #             PrestaUserModel = env['presta.users']
    #             with UserModel._assert_can_auth():
    #                 presta_user = PrestaUserModel.search([('login','=',login)], limit=1)
    #                 if not presta_user:
    #                     raise AccessDenied()
    #                 user = presta_user._check_hash(password)
    #                 raise AccessDenied("User migrated from old system, please login again.")


class PrestaUsers(models.Model):
    _name = 'presta.users'
    _description = 'Presta Users'

    _rec_name = 'login'
    _order = 'login ASC'

    login = fields.Char(required=True)
    hashpw = fields.Char(required=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            'login_unique',
            'unique(login)',
            _('Login must be unique')
        )
    ]

    
    @api.model
    def create(self, values):
        hashpw = values['hashpw']
        if len(hashpw) == 32:
            values['hashpw'] = bcrypt.hashpw(hashpw.encode('utf-8'), bcrypt.gensalt())
        result = super(PrestaUsers, self).create(values)
        return result
    

    @api.model
    def _check_hash(self, password=None):
        self.ensure_one()
        if not password:
            return
        match = False
        hashpw = self.hashpw.encode('utf-8')
        login = self.login
        user = self.env['res.users'].search([('login','=',login)], limit=1)
        if user:
            return
        if bcrypt.checkpw(password.encode('utf-8'), hashpw):
            match = True
        else:
            md5_hash = hashlib.md5((salt + password).encode('utf-8')).hexdigest()
            if bcrypt.checkpw(md5_hash.encode('utf-8'), hashpw):
                match = True
        if not match:
            return
        ResPartner = self.env['res.partner']
        partner = ResPartner.search([('email','=',self.login)], limit=1, order='parent_id DESC')
        if not partner:
            partner = ResPartner.create({'name': login, 'email': login})
        wizard = self.env['portal.wizard'].with_context(active_ids=partner.ids).create({})
        wizard.user_ids.write({'in_portal': True})
        wizard.action_apply()
        user = partner.user_ids[:1]
        cp_wiz = self.env['change.password.wizard'].create({
            'user_ids': [(0, 0, {
                'user_id': user.id,
                'user_login': login,
                'new_passwd': password
            })]
        })
        cp_wiz.change_password_button()
        self.write({'active': False})
        self.env.cr.commit()
    
