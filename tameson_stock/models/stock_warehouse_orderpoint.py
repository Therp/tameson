from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _


class StockWarehouseOrderpoint(models.Model):
    _inherit = 'stock.warehouse.orderpoint'

    rr_supplier = fields.Char(string=_('Supplier'), compute='_compute_rr_supplier', store=True)
    rr_out_3m = fields.Integer(string=_('Out 3M'), compute='_compute_rr_out_3m', store=True)
    rr_out_12m = fields.Integer(string=_('Out 12M'), compute='_compute_rr_out_12m', store=True)
    rr_max_out_3m = fields.Float(string=_('Max/out 3M'), compute='_compute_rr_max_out_3m', store=True)
    rr_count_3m = fields.Integer(string=_('Count 3M'), compute='_compute_rr_count_3m', store=True)
    rr_count_12m = fields.Integer(string=_('Count 12M'), compute='_compute_rr_count_12m', store=True)

    @api.model
    def create(self, vals):
        ret = super(StockWarehouseOrderpoint, self).create(vals)

        self._compute_rr()

        return ret

    def write(self, vals):
        ret = super(StockWarehouseOrderpoint, self).write(vals)

        if not self.env.context.get('rr_computing'):
            self._compute_rr()

        return ret

    @api.model
    def _migrate_rr(self):
        self.env['stock.warehouse.orderpoint'].search([])._compute_rr()

    @api.model
    def cron_recompute_rr(self):
        self.env['stock.warehouse.orderpoint'].search([])._compute_rr()

    @api.model
    def cron_validate_orderpoint_product_routes(self):
        mtomts_id = self.env['stock.location.route'].search([['name', '=', 'Make To Order + Make To Stock']])[0]
        buy_id = self.env['stock.location.route'].search([['name', '=', 'Buy']])[0]

        orderpoint_route_ids = sorted([buy_id.id])
        non_orderpoint_route_ids = sorted([mtomts_id.id, buy_id.id])

        # First step – remove orderpoints with min/max qty = 0
        self.env['stock.warehouse.orderpoint'].search([('product_max_qty', '<=', 0.0)]).unlink()

        # Second step: fix products
        orderpoints = self.env['stock.warehouse.orderpoint'].search_read([], ['product_id'])
        orderpoint_pp_ids = set(swo['product_id'][0] for swo in orderpoints)
        orderpoint_pt_ids = set(
            pp['product_tmpl_id'][0]
            for pp in self.env['product.product'].search_read([['id', 'in', list(orderpoint_pp_ids)]], ['product_tmpl_id'])
        )
        wrong_orderpoint_pt_ids = set(
            pt['id']
            for pt in self.env['product.template'].search_read([['id', 'in', list(orderpoint_pt_ids)]], ['id', 'route_ids'])
            if sorted(pt['route_ids']) != orderpoint_route_ids
        )
        if wrong_orderpoint_pt_ids:
            # fix products
            self.env['product.template'].browse(list(wrong_orderpoint_pt_ids)).write({'route_ids': orderpoint_route_ids})

        non_orderpoint_pt_ids = set(
            pt['id']
            for pt in self.env['product.template'].search_read([['id', 'not in', list(orderpoint_pt_ids)]], ['id'])
        )
        wrong_non_orderpoint_pt_ids = set(
            pt['id']
            for pt in self.env['product.template'].search_read([['id', 'in', list(non_orderpoint_pt_ids)]], ['id', 'route_ids'])
            if sorted(pt['route_ids']) != non_orderpoint_route_ids
        )
        if wrong_non_orderpoint_pt_ids:
            # fix products
            self.env['product.template'].browse(list(wrong_non_orderpoint_pt_ids)).write({'route_ids': non_orderpoint_route_ids})

    @api.model
    def fix_product_route(self):
        pt = self.product_id.product_tmpl_id

        buy_id = self.env['stock.location.route'].search([['name', '=', 'Buy']])[0]

        pt.route_ids = [(6, 0, [buy_id.id])]

    def _compute_rr(self):
        self._compute_rr_supplier()
        # No need to compute rr_out_3m as it's computed in rr_max_out_3m
        # self._compute_rr_out_3m()
        self._compute_rr_out_12m()
        self._compute_rr_max_out_3m()
        self._compute_rr_count_3m()
        self._compute_rr_count_12m()

    def _compute_rr_supplier(self):
        if not self.ids:
            return

        query = """
        SELECT swo.id, rp.name
          FROM stock_warehouse_orderpoint AS swo
          JOIN product_product AS pp
            ON pp.id = swo.product_id
          JOIN product_supplierinfo AS psi
            ON (psi.product_id = pp.id OR psi.product_tmpl_id = pp.product_tmpl_id)
          JOIN res_partner AS rp
            ON psi.name = rp.id
          WHERE swo.id IN %(swo_ids)s
        """

        self.env.cr.execute(query, {
            'swo_ids': tuple(self.ids),
        })

        suppliers = {
            row[0]: row[1]
            for row in self.env.cr.fetchall()
        }

        self._rr_bulk_update('rr_supplier', suppliers, '')

    def _compute_rr_out_3m(self):
        sum_qtys = self._rr_sum_qtys('outgoing', 3)

        self._rr_bulk_update('rr_out_3m', sum_qtys, 0)

    def _compute_rr_out_12m(self):
        sum_qtys = self._rr_sum_qtys('outgoing', 12)

        self._rr_bulk_update('rr_out_12m', sum_qtys, 0)

    def _compute_rr_max_out_3m(self):
        self._compute_rr_out_3m()

        dict_data = {}

        for record in self.with_context({'rr_computing': True}):
            if not float(record.rr_out_3m):
                dict_data[record.id] = 0
            else:
                # record.rr_max_out_3m = self._rr_max_qty(record.product_id.id, 'outgoing', 3) / float(record.rr_out_3m)
                # record.rr_max_out_3m = record.product_max_qty / float(record.rr_out_3m)
                dict_data[record.id] = record.product_max_qty / float(record.rr_out_3m)

        self._rr_bulk_update('rr_max_out_3m', dict_data, 0)

    def _compute_rr_count_3m(self):
        counted = self._rr_count_pickings('outgoing', 3)

        self._rr_bulk_update('rr_count_3m', counted, 0)

    def _compute_rr_count_12m(self):
        counted = self._rr_count_pickings('outgoing', 12)

        self._rr_bulk_update('rr_count_12m', counted, 0)

    def _rr_bulk_update(self, field_name, dict_data, default_value=None):
        for r in self:
            if r.id not in dict_data:
                dict_data[r.id] = default_value

        for record in self.with_context({'rr_computing': True}):
            try:
                setattr(record, field_name, dict_data[record.id])
            except KeyError:
                setattr(record, field_name, default_value)

    def _rr_count_pickings(self, picking_type_code, months):
        move_lines_dict = self._rr_move_lines_dict(picking_type_code, months, operator='COUNT(*)')

        return {
            record.id: move_lines_dict.get(record.product_id.id, 0)
            for record in self
        }

    def _rr_sum_qtys(self, picking_type_code, months):
        move_lines_dict = self._rr_move_lines_dict(picking_type_code, months, operator='SUM(sm.product_qty)')

        return {
            record.id: move_lines_dict.get(record.product_id.id, 0)
            for record in self
        }

    def _rr_move_lines_dict(self, picking_type_code, months, operator='COUNT(*)'):
        if not self.ids:
            return {}

        query = """
        SELECT sm.product_id, {operator}
          FROM stock_move AS sm
          JOIN stock_picking AS sp
            ON sp.id = sm.picking_id
          JOIN stock_picking_type AS spt
            ON spt.id = sp.picking_type_id
          WHERE sp.scheduled_date >= (now() - '{months} months'::interval)
          AND sm.product_id IN %(product_ids)s
          AND spt.code = %(picking_type_code)s
          AND sp.state != %(state)s
          GROUP BY sm.product_id
        """.format(months=months, operator=operator)

        # scheduled_date = (datetime.now() - relativedelta(months=months)).isoformat()

        self.env.cr.execute(query, {
            # 'scheduled_date': scheduled_date,
            'months': months,
            'picking_type_code': picking_type_code,
            'product_ids': tuple(r.product_id.id for r in self),
            'state': 'cancel',
        })

        return {
            row[0]: row[1]
            for row in self.env.cr.fetchall()
        }
