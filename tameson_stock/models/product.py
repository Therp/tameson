import logging
from datetime import datetime, timedelta
from collections import Counter
from odoo import api, fields, models, _
from odoo.tools.float_utils import float_round
from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT as DSDF

_logger = logging.getLogger(__name__)

def list_split(listA, n):
    for start in range(0, len(listA), n):
        stop = len(listA) if len(listA) < n+start else n+start
        every_chunk = listA[start: stop]
        yield every_chunk

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

    minimal_qty_available = fields.Float(
        compute='_minimal_qty_available',
        digits='Product Unit of Measure',
        string=_('Minimal QTY Available'),
        help="Compute minimal QTY available in the future, including incoming "
             "and outgoing pickings."
    )

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

    route_ids = fields.Many2many(default=lambda self: self._get_buy_route())
    wh_id = fields.Many2one(string="Product Warehouse", comodel_name='stock.warehouse',ondelete='restrict',)    

    def _get_buy_route(self):
        mtos_id = self.env.ref('stock_mts_mto_rule.route_mto_mts', raise_if_not_found=False)
        res = super(ProductTemplate, self)._get_buy_route()
        if mtos_id:
            res.append(mtos_id.id)
        return res

    @api.model
    def set_buy_route(self):
        buy_id = self.env.ref('purchase_stock.route_warehouse0_buy')
        self.write({'route_ids': [(6, 0, [buy_id.id])]})

    @api.model
    def set_mtos_buy_route(self):
        buy_id = self.env.ref('purchase_stock.route_warehouse0_buy')
        mtos_id = self.env.ref('stock_mts_mto_rule.route_mto_mts')
        self.write({'route_ids': [(6, 0, [buy_id.id, mtos_id.id])]})

    def write(self, vals):
        res = super(ProductTemplate, self).write(vals)
        warehouse_id = vals.get('wh_id', False)
        if warehouse_id:
            rules = self.product_variant_id.orderpoint_ids
            rules.write({
                'warehouse_id': warehouse_id
            })
            rules.onchange_warehouse_id()
        return res

    @api.model
    def _search_has_reordering_rules(self, operator, operand):
        if not isinstance(operand, bool):
            return []
        if operator not in ('!=', '='):
            return []
        self._cr.execute("""
        SELECT pp.product_tmpl_id FROM stock_warehouse_orderpoint swo
        LEFT JOIN product_product pp on pp.id = swo.product_id
        WHERE swo.product_min_qty != 0
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
            AND swo.product_min_qty != 0
        """, self.mapped('product_variant_ids').ids)
        have_rules = dict(self._cr.fetchall())
        for product in self:
            product.rr_has_reordering_rules = have_rules.get(product.product_variant_id.id, False)

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


    def cron_recompute_min_qty_avail(self):
        lasthour = datetime.now() - timedelta(hours=1)
        lasthour_formatted = lasthour.strftime(DSDF)
        domain = ['|', ('create_date', '>', lasthour_formatted),
                  ('write_date', '>', lasthour_formatted)]
        to_update_products = self.env['stock.move.line'].search(domain).mapped(
            'product_id') + self.env['stock.move'].search(domain).mapped(
                'product_id')
        to_update_pts = to_update_products.mapped('product_tmpl_id')
        to_update_pts._minimal_qty_available_stored()
        ## set bom lead updated
        to_update_pts.mapped('bom_ids').with_delay().set_bom_lead()
        ## non-bom-lead
        for pos in range(0, len(to_update_pts), 5000):
            to_update_pts[pos:pos+5000].with_delay().set_non_bom_lead()

    def cron_recompute_all_min_qty_avail_stored_tmpl(self):
        to_update_products = self.env['stock.move'].search([]).mapped(
                'product_id')
        to_update_products.mapped('product_tmpl_id')._minimal_qty_available_stored()
        boms = self.env['mrp.bom'].search([])
        for pos in range(0, len(boms), 30000):
            boms[pos:pos+30000].with_delay().set_bom_lead()


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

    def _minimal_qty_available_stored(self, field_names=None, arg=False):
        if not self:
            return
        CeleryTask = self.env['celery.task']
        bom_product_query = '''
SELECT DISTINCT mb.product_tmpl_id FROM product_product pp
    LEFT JOIN mrp_bom_line bl ON bl.product_id = pp.id
    LEFT JOIN mrp_bom mb ON mb.id = bl.bom_id
WHERE pp.id IN (%s)''' % ','.join(map(str, self.mapped('product_variant_ids').ids))
        self.env.cr.execute(bom_product_query)
        bom_products = [item[0] for item in self.env.cr.fetchall()]
        to_update_product_tmpls = self + self.browse(bom_products)
        split_size = 1000
        for pos in range(0, len(to_update_product_tmpls), split_size):
            to_update_product_tmpls[pos:pos+split_size].with_delay().store_min_qty_jobs()


    def store_min_qty_jobs(self):
        for pt in self:
            pt.write({'minimal_qty_available_stored': pt.minimal_qty_available})
        return True