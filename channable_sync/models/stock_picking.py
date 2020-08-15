from odoo import api, fields, models, _


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_done(self):
        res = super(StockPicking, self).action_done()

        # mark sale orders that need to be updated to Channable
        self.filtered(lambda p: p.sale_id and p.sale_id.channable_order_id).mapped('sale_id').write({'channable_to_update_shipped': True})

        return res
