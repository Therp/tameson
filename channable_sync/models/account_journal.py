from odoo import api, fields, models, _


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    channable_channel_name = fields.Char(string="Channable Channel Name", help="Name of the channel in Channable, to link and register the payment on this journal.")
