import logging
from datetime import datetime, timedelta
from collections import Counter
from odoo import api, fields, models, _
from odoo.tools.float_utils import float_round
from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT as DSDF

_logger = logging.getLogger(__name__)


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

    def _get_min_components_needs(self, bom):
        bom_components = bom.explode(self, 1.0)[1]
        needs = Counter()
        for bom_line, bom_component in bom_components:
            # product_uom_id = bom_component['product_uom']
            component = bom_line.product_id
            # if product_uom_id not in cache['product_uom']:
            #     cache['product_uom'][product_uom_id] = \
            #           self.env['product.uom'].browse(
            #           product_uom_id)
            # product_uom = cache['product_uom'][product_uom_id]
            if component.type != 'product':
                continue
            # component_qty = self.env['product.uom']._compute_qty_obj(
            #     product_uom,
            #     bom_component['product_qty'],
            #     component.uom_id
            # )
            needs += Counter(
                {component: bom_component['qty']}
            )
        return needs

    # NOTE: this doesn't work for kits, it's just mightly complicated
    def _minimal_qty_available(self, field_names=None, arg=False):
        context = self.env.context or {}
        field_names = field_names or []
        domain_products = [('product_id', 'in', self.ids)]
        domain_quant, domain_move_in, domain_move_out = [], [], []

        domain_quant_loc, domain_move_in_loc, domain_move_out_loc = \
            self._get_domain_locations()
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
        quants = dict(
            map(lambda x: (x['product_id'][0], x['quantity']), quants))

        ctx = context.copy()
        ctx.update({'prefetch_fields': False})

        for product in self:
            # section with bom calculations
            if product.bom_ids:
                bom_products = self.env['product.product'].search([
                    ['id', 'in', self.ids],
                    ['bom_ids', '!=', False],
                ])
                non_bom_products = self.env['product.product'].search([
                    ['id', 'in', self.ids],
                    ['bom_ids', '=', False],
                ])
                components = bom_products.mapped(
                    'bom_ids.bom_line_ids.product_id')
                non_bom_products._minimal_qty_available()
                components._minimal_qty_available()
                for product in bom_products:
                    bom_qtys = set([0.0])
                    for bom in product.bom_ids:
                        component_needs = product._get_min_components_needs(
                            bom)
                        if not component_needs:
                            continue
                        components_min_qty = min(
                            component.minimal_qty_available // need
                            for component, need in component_needs.items()
                        )
                        # Compute with bom quantity
                        bom_qty = bom.product_uom_id._compute_quantity(
                            bom.product_qty,
                            bom.product_tmpl_id.uom_id
                        )
                        bom_qtys.add(bom_qty * components_min_qty)
                    # NOTE: when more than 2 BOM is available we take max
                    product.minimal_qty_available = max(bom_qtys)
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

    def _minimal_qty_available_stored(self, field_names=None, arg=False):
        for product in self:
            product._minimal_qty_available()
            try:
                product.minimal_qty_available_stored = \
                    product.minimal_qty_available
            except:
                pass
        _logger.info('ReCompute Update for Prs complete')

    minimal_qty_available = fields.Float(
        compute='_minimal_qty_available',
        digits='Product Unit of Measure',
        string=_('Minimal QTY Available'),
        help="Compute minimal QTY available in the future, including incoming "
             "and outgoing pickings."
    )

    minimal_qty_available_stored = fields.Float(
        digits='Product Unit of Measure',
        string=_('Minimal QTY Available pre-calculated for export'),
        store=True,
        help="Compute minimal QTY available in the future, including incoming "
             "and outgoing pickings. this is a stored field, precalculated for"
             "faster exports."
    )

    def cron_recompute_min_qty_avail(self):
        lasthour = datetime.now() - timedelta(hours=1)
        lasthour_formatted = lasthour.strftime(DSDF)
        domain = ['|', ('create_date', '>', lasthour_formatted),
                  ('write_date', '>', lasthour_formatted)]
        to_update_products = self.env['stock.move.line'].search(domain).mapped(
            'product_id') + self.env['stock.move'].search(domain).mapped(
                'product_id')
        # add products with these products in BOM
        bom_domain = [
            ('bom_ids.bom_line_ids.product_id', 'in', to_update_products.ids)]
        to_update_products += self.env['product.product'].search(
            bom_domain)
        to_update_products._minimal_qty_available_stored()

    def cron_recompute_all_min_qty_avail_stored(self):
        self.env['product.product'].search([])._minimal_qty_available_stored()

    def action_view_stock_moves(self):
        self.ensure_one()
        action = self.env.ref('stock.stock_move_action').read()[0]
        action.update({
            'domain': [('product_id', '=', self.id)],
            'context': {'create': 0, 'search_default_future': True}
        })
        return action


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
        rhs = (operator == '=' and operand) or (
            operator == '!' and not operand)
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
        _logger.info('ReCompute Update for Prtmpl complete')

    def _minimal_qty_available_stored(self, field_names=None, arg=False):
        for product in self:
            product.minimal_qty_available_stored = \
                product.minimal_qty_available

    def cron_recompute_min_qty_avail(self):
        lasthour = datetime.now() - timedelta(hours=1)
        lasthour_formatted = lasthour.strftime(DSDF)
        domain = ['|', ('create_date', '>', lasthour_formatted),
                  ('write_date', '>', lasthour_formatted)]
        to_update_product_tmpls = self.env['stock.move.line'].search(
            domain).mapped('product_id.product_tmpl_id') + self.env[
                'stock.move'].search(domain).mapped('product_tmpl_id')
        # add products with these products in BOM
        bom_domain = [
            ('bom_ids.bom_line_ids.product_id.product_tmpl_id',
             'in', to_update_product_tmpls.ids)]
        to_update_product_tmpls += self.env['product.template'].search(
            bom_domain
        )
        to_update_product_tmpls._minimal_qty_available_stored()

    def cron_recompute_all_min_qty_avail_stored_tmpl(self):
        self.env['product.template'].search([])._minimal_qty_available_stored()

    minimal_qty_available = fields.Float(
        compute='_minimal_qty_available',
        digits='Product Unit of Measure',
        string=_('Minimal QTY Available'),
        # fnct_search=_search_product_quantity,
        help="Compute minimal QTY available in the future, including incoming "
             "and outgoing pickings."
    )

    minimal_qty_available_stored = fields.Float(
        digits='Product Unit of Measure',
        string=_('Minimal QTY Available pre-calculated for export'),
        store=True,
        help="Compute minimal QTY available in the future, including incoming "
             "and outgoing pickings. this is a stored field, precalculated for"
             "faster exports."
    )

    rr_has_reordering_rules = fields.Boolean(
        compute='_compute_has_reordering_rules',
        search=_search_has_reordering_rules,
        string=_('Has reordering rules')
    )

    def action_view_stock_moves(self):
        self.ensure_one()
        action = self.env.ref('stock.stock_move_action').read()[0]
        action.update({
            'domain': [('product_id', 'in', self.product_variant_ids.ids)],
            'context': {'create': 0, 'search_default_future': True}
        })
        return action
