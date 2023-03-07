# Copyright 2020 Therp BV <https://therp.nl>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    t_aa_mutation_ids = fields.One2many(
        comodel_name="aa.mutation",
        inverse_name="purchase_id",
    )
    t_aa_purchase_id = fields.Integer(string="AA Purchase ID", copy=False, default=0)

    def find_and_refresh_picking_in_out_associations(self):
        for this in self:
            for line in this.order_line:
                # PO of POL
                # connected Sale for POL (only ongrouped origin)
                sale = line.ungrouped_origin
                if sale:
                    # picking type code = incoming
                    # we use the features from purchase_stock and sale_stock
                    # get the move of the picking associated with current POL
                    all_in_moves = this.picking_ids.move_lines
                    in_moves = self.env["stock.move"].search(
                        [
                            ("id", "in", all_in_moves.ids),
                            ("picking_code", "=", "incoming"),
                            ("purchase_line_id", "=", line.id),
                        ]
                    )
                    out_pickings = sale.picking_ids.filtered(
                        lambda l: l.move_lines.sale_line_id.order_id == sale
                    )
                    in_moves.write(
                        {"origin_so_picking_ids": [(6, 0, out_pickings.ids)]}
                    )

    def _create_picking(self):
        res = super(PurchaseOrder, self)._create_picking()
        self.find_and_refresh_picking_in_out_associations()
        return res

    def action_rfq_send(self):
        res = super(PurchaseOrder, self).action_rfq_send()
        template = self.env.ref("tameson_purchasing.tameson_template_po_supplier").id
        res["context"]["default_template_id"] = template
        return res

    class AAMutation(models.Model):
        _name = "aa.mutation"
        _description = "AA Mutation"
        _rec_name = "name"
        _order = "name ASC"

        purchase_id = fields.Many2one(
            comodel_name="purchase.order", ondelete="cascade", required=True
        )
        name = fields.Char(required=True, copy=False)
