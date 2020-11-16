from odoo import api, fields, models, _
from odoo.tools import float_compare


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # need to add this so that the tooltip widget will have necessary data to
    # render the min qty field
    minimal_qty_available = fields.Float(
        related='product_id.minimal_qty_available',
        string=_('Product min qty available'),
        readonly=True
    )

    minimal_qty_available_stored = fields.Float(
        related='product_id.minimal_qty_available_stored',
        string=_('Product min qty available stored'),
        readonly=True
    )


    @api.onchange('product_uom_qty', 'product_uom', 'product_id')
    def _onchange_product_id_check_min_availability(self):
        if not self.product_id or not self.product_uom_qty or not self.product_uom:
            return {}
        if self.product_id.type == 'product':
            precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
            if float_compare(self.product_id.minimal_qty_available, self.product_uom_qty, precision_digits=precision) == -1:
                warning_mess = {
                    'title': _('Not enough inventory!'),
                    'message': _('You plan to sell %.2f %s but the minimum qty available is %.2f %s !\nThe current stock on hand is %.2f %s.') %
                    (self.product_uom_qty, self.product_uom.name, self.product_id.minimal_qty_available, self.product_id.uom_id.name, self.product_id.qty_available, self.product_id.uom_id.name)
                }
                return {'warning': warning_mess}
        return {}
