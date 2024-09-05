###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_is_zero


class PurchaseOrder(models.Model):
    _name = "purchase.order"
    _inherit = ["purchase.order", "set.help.mixin"]

    is_product_supplier = fields.Boolean(
        default=True, compute="get_is_product_supplier"
    )

    t_done_pickings = fields.Many2many(
        "stock.picking",
        string=_("Done pickings for this purchase order"),
        compute="_compute_t_done_pickings",
    )

    t_clipboard_text_handle = fields.Char(
        string="Products Quantity (Clipboard)",
        compute="_compute_clipboard_text_handle",
    )

    t_aa_mutation_ids = fields.One2many(
        comodel_name="aa.mutation",
        inverse_name="purchase_id",
    )
    t_aa_purchase_id = fields.Integer(string="AA Purchase ID", copy=False, default=0)

    purchase_confirmation = fields.Boolean()
    aa_comm_id = fields.Many2one(
        string="AA Communication",
        comodel_name="aa.comm",
        ondelete="cascade",
        readonly=True,
    )

    @api.model
    def create(self, vals):
        res = super().create(vals)
        res.aa_comm_id = self.env["aa.comm"].create(
            {
                "name": res.name,
                "purchase_id": res.id,
            }
        )
        return res

    def button_confirm(self):
        for order in self:
            if not order.picking_type_id.warehouse_id.code == "AA-NL":
                continue
            products = []
            for line in order.order_line:
                if line.product_id.id not in products:
                    products.append(line.product_id.id)
                else:
                    raise ValidationError(
                        _(
                            'Following SKU appears on multipel lines: "%s"\n\
This is not allowed for ActiveAnts, please review the PO and combine the lines'
                            % line.product_id.default_code
                        )
                    )
        return super().button_confirm()

    def get_is_product_supplier(self):
        for po in self:
            if po.partner_id and not po.partner_id.is_product_supplier:
                po.is_product_supplier = False
            else:
                po.is_product_supplier = True

    def action_rfq_send(self):
        res = super(PurchaseOrder, self).action_rfq_send()
        template = self.env.ref("tameson_purchasing.tameson_template_po_supplier").id
        res["context"]["default_template_id"] = template
        return res

    def _compute_clipboard_text_handle(self):
        for po in self:
            text = ""
            for po_line in po.order_line:
                supplier_rec = po_line.product_id.seller_ids.filtered(
                    lambda v: v.partner_id == po.partner_id
                )
                if supplier_rec and supplier_rec[0].product_code:
                    product_code = supplier_rec[0].product_code
                else:
                    product_code = po_line.product_id.default_code or ""
                if product_code.startswith("LDS-"):
                    continue
                if po_line.move_dest_ids:
                    total = 0
                    for line in po_line.move_dest_ids:
                        total += line.product_uom_qty
                        text += "%s\t%s\n" % (str(line.product_uom_qty), product_code)
                    difference = po_line.product_qty - total
                    if not float_is_zero(difference, precision_digits=2):
                        text += "%s\t%s\n" % (str(difference), product_code)
                else:
                    text += "%s\t%s\n" % (str(po_line.product_qty), product_code)
            po.t_clipboard_text_handle = text

    @api.depends("picking_ids.state")
    def _compute_t_done_pickings(self):
        for r in self:
            r.t_done_pickings = r.picking_ids.filtered(
                lambda picking: picking.state == "done"
            )


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    max_reorder = fields.Float(compute="_get_max_reorder", digits=(4, 2))
    max_reorder_percentage = fields.Float(
        string=_("Percentage"), compute="_get_max_reorder", digits=(4, 2)
    )
    origin_so_ids = fields.Many2many("sale.order", compute="_get_so_origins")

    def action_open_origin_so(self):
        action = self.env.ref("sale.action_orders").read()[0]
        if len(self.origin_so_ids) == 1:
            action["res_id"] = self.origin_so_ids[:1].id
            action["views"] = [(False, "form")]
        else:
            action["domain"] = [("id", "in", self.origin_so_ids.ids)]
        return action

    def _get_so_origins(self):
        for line in self:
            line.origin_so_ids = line.move_dest_ids.mapped("picking_id").mapped(
                "sale_id"
            )

    def _get_max_reorder(self):
        for line in self:
            reorder = line.product_id.orderpoint_ids[:1]
            if not reorder or not reorder.product_max_qty:
                line.max_reorder = 0
                line.max_reorder_percentage = 0
            else:
                line.max_reorder = reorder.product_max_qty
                line.max_reorder_percentage = (
                    reorder.product_min_qty / reorder.product_max_qty * 100
                )


class AAMutation(models.Model):
    _name = "aa.mutation"
    _description = "AA Mutation"
    _rec_name = "name"
    _order = "name ASC"

    purchase_id = fields.Many2one(
        comodel_name="purchase.order", ondelete="cascade", required=True
    )
    name = fields.Char(required=True, copy=False)


class AAComm(models.Model):
    _inherit = "aa.comm"

    purchase_id = fields.Many2one(
        comodel_name="purchase.order",
        ondelete="cascade",
    )

    def get_search_string(self):
        if self.purchase_id:
            return "purchase"
        else:
            return super().get_search_string()


class PurchaseOrderCSV(models.AbstractModel):
    _name = "report.tameson_purchasing.po_csv"
    _inherit = "report.report_csv.abstract"

    def generate_csv_report(self, writer, data, doc_ids):
        writer.writeheader()
        for line in doc_ids.mapped("order_line"):
            writer.writerow(
                {
                    "Supplier SKU": line.product_id.supplierinfo_code,
                    "QTY": int(line.product_qty),
                }
            )

    def csv_report_options(self):
        res = super().csv_report_options()
        res["fieldnames"].append("Supplier SKU")
        res["fieldnames"].append("QTY")
        res["delimiter"] = ";"
        res["quoting"] = 0
        return res


class ModelName(models.Model):
    _name = "purchase.orderline.csv.import.line"


class ModelName1(models.Model):
    _name = "purchase.orderline.csv.import"
