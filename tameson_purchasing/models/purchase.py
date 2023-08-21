###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare, float_is_zero


class PurchaseOrder(models.Model):
    _name = "purchase.order"
    _inherit = ["purchase.order", "set.help.mixin"]

    is_product_supplier = fields.Boolean(
        default=True, compute="get_is_product_supplier"
    )
    t_purchase_method = fields.Selection(
        [
            ("purchase", "Ordered quantities"),
            ("receive", "Delivered quantities"),
        ],
        string=_("Control Policy (overrides product control policies)"),
        default="purchase",
        required=True,
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
        ondelete="restrict",
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

    # compute invoice_status based on t_purchase_method instead of each product purchase_method
    @api.depends(
        "state",
        "order_line.qty_invoiced",
        "order_line.qty_received",
        "order_line.product_qty",
        "t_purchase_method",
    )
    def _get_invoiced(self):
        precision = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )
        for order in self:
            if order.state not in ("purchase", "done"):
                order.invoice_status = "no"
                continue

            if any(
                float_compare(
                    line.qty_invoiced,
                    line.product_qty
                    if order.t_purchase_method == "purchase"
                    else line.qty_received,
                    precision_digits=precision,
                )
                == -1
                for line in order.order_line.filtered(lambda l: not l.display_type)
            ):
                order.invoice_status = "to invoice"
            elif (
                all(
                    float_compare(
                        line.qty_invoiced,
                        line.product_qty
                        if order.t_purchase_method == "purchase"
                        else line.qty_received,
                        precision_digits=precision,
                    )
                    >= 0
                    for line in order.order_line.filtered(lambda l: not l.display_type)
                )
                and order.invoice_ids
            ):
                order.invoice_status = "invoiced"
            else:
                order.invoice_status = "no"

    def _compute_clipboard_text_handle(self):
        for po in self:
            text = ""
            for po_line in po.order_line:
                supplier_rec = po_line.product_id.seller_ids.filtered(
                    lambda v: v.name == po.partner_id
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

    @api.onchange("partner_id")
    def _onchange_partner_id_change_t_purchase_method(self):
        for r in self:
            if r.partner_id:
                term_id = r.partner_id.property_supplier_payment_term_id
                if term_id:
                    if term_id.t_invoice_delivered_quantities:
                        r.t_purchase_method = "receive"
                    else:
                        r.t_purchase_method = "purchase"
                else:
                    r.t_purchase_method = "purchase"

    @api.depends("picking_ids.state")
    def _compute_t_done_pickings(self):
        for r in self:
            r.t_done_pickings = r.picking_ids.filtered(
                lambda picking: picking.state == "done"
            )

    def _create_invoice(self, send_email=True):
        if self.invoice_status == "invoiced":
            return

        invoice_ids = set(self.invoice_ids.ids)

        view = self.with_context(create_bill=True).action_view_invoice()
        ctx = view["context"]
        vals = {}
        for k, v in ctx.items():
            if k.startswith("default_"):
                fname = k.replace("default_", "")
                vals[fname] = v
        inv = self.env["account.move"].new(vals)
        inv.purchase_id = self
        inv._onchange_purchase_auto_complete()
        vals = {}

        for fname, f in inv._fields.items():
            try:
                v = f.convert_to_write(getattr(inv, fname), inv)
                vals[fname] = v
            except TypeError:  # error for NewId, skip such fields, TODO maybe there's a better way
                continue
        inv.create(vals)

        new_invoice_ids = self.invoice_ids.filtered(
            lambda inv: inv.id not in invoice_ids
        )
        new_invoice_ids.action_post()

        if send_email:
            view_data = new_invoice_ids.with_context(
                active_id=self.id,
                active_ids=self.ids,
                active_model="purchase.order",
                default_invoice_origin=self.name,
                default_partner_id=self.partner_id.id,
            ).action_invoice_sent()
            ctx = dict(active_ids=new_invoice_ids.ids, **view_data["context"])
            send_id = (
                self.env[view_data["res_model"]]
                .with_context(**ctx)
                .create(
                    {
                        "composition_mode": "comment",
                        "invoice_ids": [(6, None, new_invoice_ids.ids)],
                        "is_email": True,
                        "partner_id": self.partner_id.id,
                        "template_id": ctx["default_template_id"],
                    }
                )
            )
            # This is to trigger template_id change, to fill in template's
            # subject and body
            send_id.onchange_template_id()
            print_data = send_id.with_context(**ctx).send_and_print_action()
            report = (
                self.env["ir.actions.report"]
                .sudo()
                .search(
                    [
                        ["report_file", "=", print_data["report_file"]],
                        ["report_name", "=", print_data["report_name"]],
                        ["report_type", "=", print_data["report_type"]],
                    ]
                )
            )
            report.render_qweb_pdf(new_invoice_ids.ids)


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    t_purchase_method = fields.Selection(
        [
            ("purchase", "Ordered quantities"),
            ("receive", "Delivered quantities"),
        ],
        string=_("Control Policy (overrides product control policies)"),
        compute="_get_t_purchase_method",
    )
    minimal_qty_available = fields.Float(
        related="product_id.minimal_qty_available",
        string=_("Min qty"),
        readonly=True,
    )
    max_reorder = fields.Float(compute="_get_max_reorder", digits=(4, 2))
    max_reorder_percentage = fields.Float(
        string=_("Percentage"), compute="_get_max_reorder", digits=(4, 2)
    )
    origin_so_ids = fields.Many2many("sale.order", compute="_get_so_origins")

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

    @api.depends(
        "order_id.t_purchase_method", "product_id.purchase_method", "product_id.type"
    )
    def _get_t_purchase_method(self):
        for line in self:
            if line.product_id.type == "product":
                line.t_purchase_method = (
                    line.order_id.t_purchase_method or line.product_id.purchase_method
                )
            else:
                line.t_purchase_method = line.product_id.purchase_method

    # Some overrides for Odoo base code
    # SO-44999: use t_purchase_method instead of product_id.purchase_method
    def _prepare_account_move_line(self, move):
        self.ensure_one()
        if self.t_purchase_method == "purchase":
            qty = self.product_qty - self.qty_invoiced
        else:
            qty = self.qty_received - self.qty_invoiced
        if float_compare(qty, 0.0, precision_rounding=self.product_uom.rounding) <= 0:
            qty = 0.0

        if self.currency_id == move.company_id.currency_id:
            currency = False
        else:
            currency = move.currency_id

        return {
            "name": "%s: %s" % (self.order_id.name, self.name),
            "move_id": move.id,
            "currency_id": currency and currency.id or False,
            "purchase_line_id": self.id,
            "date_maturity": move.invoice_date_due,
            "product_uom_id": self.product_uom.id,
            "product_id": self.product_id.id,
            "price_unit": self.price_unit,
            "quantity": qty,
            "partner_id": move.partner_id.id,
            "analytic_account_id": self.account_analytic_id.id,
            "analytic_tag_ids": [(6, 0, self.analytic_tag_ids.ids)],
            "tax_ids": [(6, 0, self.taxes_id.ids)],
            "display_type": self.display_type,
        }


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
        ondelete="restrict",
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
                    "Supplier SKU": line.product_id.default_code,
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
