###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import api, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    t_aa_name = fields.Char("Active Ant Name", compute="_get_t_aa_name")
    t_aa_id = fields.Char("Active Ant ID", copy=False)
    t_aa_url = fields.Char("ActiveAnt URL", compute="get_t_aa_url")
    t_aa_allow_cancel = fields.Boolean(
        string="AA Allow Cancellation",
        default=False,
        track_visibility="onchange",
        copy=False,
    )
    t_aa_track_url = fields.Char("Active Ant tracktraceUrl", readonly=True, copy=False)
    source_so_id = fields.Many2one(comodel_name="sale.order", compute="_get_source_so")

    @api.depends("t_aa_id")
    def get_t_aa_url(self):
        for record in self:
            record.t_aa_url = (
                "https://maya.activeants.nl/en/client/order/detail/%s" % self.t_aa_id
            )

    @api.depends("origin")
    def _get_source_so(self):
        for record in self:
            record.source_so_id = self.env["sale.order"].search(
                [("name", "=", record.origin)], limit=1
            )

    @api.depends("name", "sale_id")
    def _get_t_aa_name(self):
        for record in self:
            record.t_aa_name = "%s - %s" % (record.sale_id.name, record.name)

    def _compute_carrier_tracking_url(self):
        for picking in self.filtered(lambda l: l.t_aa_track_url):
            picking.carrier_tracking_url = picking.t_aa_track_url
        super(
            StockPicking, self.filtered(lambda l: not l.t_aa_track_url)
        )._compute_carrier_tracking_url()

    def action_cancel(self):
        message = "Please check the transfer from ActiveAnts and check the 'AA Allow Cancellation' checkbox \n\
if it is cancelled on active ants.\n\
https://maya.activeants.nl/en/client/order/detail/%s"
        for picking in self:
            if picking.t_aa_id and not picking.t_aa_allow_cancel:
                raise UserError(message % picking.t_aa_id)
        return super().action_cancel()


class StockMove(models.Model):
    _inherit = "stock.move"

    t_aa_comm_price = fields.Float("Commercial Price", compute="_get_commercial_price")
    t_aa_comm_taxrate = fields.Float("Tax Rate", compute="_get_commercial_price")
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        ondelete="restrict",
        compute="_get_commercial_price",
    )

    @api.depends("sale_line_id")
    def _get_commercial_price(self):
        for move in self:
            commercial_price = 0
            currency = move.company_id.currency_id
            if move.sale_line_id:
                sale_line = move.sale_line_id
                sale_product = sale_line.product_id
                bom_kit = self.env["mrp.bom"]._bom_find(
                    product=sale_product, bom_type="phantom"
                )
                if bom_kit:
                    total_qty = sum(bom_kit.bom_line_ids.mapped("product_qty"))
                    commercial_price = (
                        sale_line.price_total / sale_line.product_uom_qty
                    ) / total_qty
                else:
                    commercial_price = sale_line.price_total / sale_line.product_uom_qty
                tax_rate = move.sale_line_id.tax_id[:1].amount
                currency = sale_line.currency_id
            if not commercial_price:
                commercial_price = move.product_id.list_price
                tax_rate = 0
            move.currency_id = currency
            move.t_aa_comm_price = commercial_price
            move.t_aa_comm_taxrate = tax_rate
