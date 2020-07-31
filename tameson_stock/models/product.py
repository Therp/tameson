import datetime
from odoo import api, fields, models, _
from odoo.tools.float_utils import float_round


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _get_domain_dates(self):
        from_date = self.env.context.get('from_date', False)
        to_date = self.env.context.get('to_date', False)
        domain = []
        if from_date:
            domain.append(('date', '>=', from_date))
        if to_date:
            domain.append(('date', '<=', to_date))
        return domain

    # NOTE: this doesn't work for kits, it's just mightly complicated
    def _minimal_qty_available(self, field_names=None, arg=False):
        context = self.env.context or {}
        field_names = field_names or []

        domain_products = [('product_id', 'in', self.ids)]
        domain_quant, domain_move_in, domain_move_out = [], [], []

        domain_quant_loc, domain_move_in_loc, domain_move_out_loc = self._get_domain_locations()
        domain_move_in += self._get_domain_dates() + [
            ('state', 'not in', ('done', 'cancel', 'draft'))
        ]
        domain_move_out += self._get_domain_dates() + [
            ('state', 'not in', ('done', 'cancel', 'draft'))
        ]
        domain_quant += domain_products

        if context.get('lot_id'):
            domain_quant.append(('lot_id', '=', context['lot_id']))
        if context.get('owner_id'):
            domain_quant.append(('owner_id', '=', context['owner_id']))
            owner_domain = ('restrict_partner_id', '=', context['owner_id'])
            domain_move_in.append(owner_domain)
            domain_move_out.append(owner_domain)
        if context.get('package_id'):
            domain_quant.append(('package_id', '=', context['package_id']))

        domain_move_in += domain_move_in_loc
        domain_move_out += domain_move_out_loc
        domain_quant += domain_quant_loc

        quants = self.env['stock.quant'].read_group(
            domain_quant,
            ['product_id', 'quantity'], ['product_id']
        )
        quants = dict(map(lambda x: (x['product_id'][0], x['quantity']), quants))

        ctx = context.copy()
        ctx.update({'prefetch_fields': False})

        for product in self:
            if product.bom_ids:
                product.minimal_qty_available = False
                continue

            domain_product = [('product_id', '=', product.id)]

            moves_in = self.env['stock.move'].search_read(
                domain_move_in + domain_product,
                ['product_id', 'product_qty', 'date_expected'],
                order='date_expected'
            )
            moves_out = self.env['stock.move'].search_read(
                domain_move_out + domain_product,
                ['product_id', 'product_qty', 'date_expected'],
                order='date_expected'
            )
            for move in moves_in:
                move['_type'] = 'in'
                if not move['date_expected']:
                    raise Exception('Date expected for move is empty')
            for move in moves_out:
                move['_type'] = 'out'
                if not move['date_expected']:
                    raise Exception('Date expected for move is empty')
            moves_all = moves_in + moves_out
            moves_all.sort(key=lambda move: move['date_expected'])

            min_qty = quants.get(product.id, 0.0)
            qty = min_qty
            for move in moves_all:
                if move['_type'] == 'in':
                    qty += move['product_qty']
                else:
                    qty -= move['product_qty']
                if qty < min_qty:
                    min_qty = qty

            product.minimal_qty_available = float_round(
                min_qty,
                precision_rounding=product.uom_id.rounding
            )

    minimal_qty_available = fields.Float(
        compute='_minimal_qty_available',
        digits='Product Unit of Measure',
        string=_('Minimal QTY Available'),
        help="Compute minimal QTY available in the future, including incoming "
             "and outgoing pickings."
    )


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model
    def _search_has_reordering_rules(self, operator, operand):
        if not isinstance(operand, bool):
            return []
        if operator not in ('!=', '='):
            return []
        self._cr.execute("""
        SELECT product_id FROM stock_warehouse_orderpoint
        """)
        product_ids = [row[0] for row in self._cr.fetchall()]
        rhs = (operator == '=' and operand) or (operator == '!' and not operand)
        if rhs:
            return [('id', 'in', product_ids)]
        return [('id', 'not in', product_ids)]

    def _compute_has_reordering_rules(self):
        self._cr.execute("""
        SELECT product_id, true FROM stock_warehouse_orderpoint
            WHERE product_id in %s
        """, [self.ids])
        have_rules = dict(self._cr.fetchall())
        for product in self:
            product.rr_has_reordering_rules = have_rules.get(product.id, False)

    def _minimal_qty_available(self, field_names=None, arg=False):
        for product in self:
            if product.bom_ids:
                product.minimal_qty_available = False
                continue

            variant_available = product.product_variant_ids
            variant_available._minimal_qty_available()
            try:
                product.minimal_qty_available = min(
                    (
                        pv.minimal_qty_available
                        for pv in variant_available
                        if pv.minimal_qty_available
                    )
                )
            except ValueError:
                product.minimal_qty_available = False

    minimal_qty_available = fields.Float(
        compute='_minimal_qty_available',
        digits='Product Unit of Measure',
        string=_('Minimal QTY Available'),
        # fnct_search=_search_product_quantity,
        help="Compute minimal QTY available in the future, including incoming "
             "and outgoing pickings."
    )

    rr_has_reordering_rules = fields.Boolean(
        compute='_compute_has_reordering_rules',
        search=_search_has_reordering_rules,
        string=_('Has reordering rules')
    )
