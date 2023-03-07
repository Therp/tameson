import base64
import codecs
import itertools
import re
from datetime import datetime

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.pdf import merge_pdf


class StockPicking(models.Model):
    _name = "stock.picking"
    _inherit = ["stock.picking", "set.help.mixin"]

    t_delivery_allowed = fields.Boolean(
        compute="_t_delivery_allowed_get",
        string=_("Delivery allowed"),
        store=True,
        readonly=False,
    )
    t_invoice_ids_to_report = fields.Many2many(
        "account.move",
        compute="_compute_t_invoice_ids_to_report",
        string=_("Invoices to report"),
    )
    t_partner_outside_eu = fields.Boolean(
        string=_("Out of EU"),
        compute="_get_t_partner_outside_eu",
        search="_search_t_partner_outside_eu",
        readonly=True,
    )
    t_payment_status = fields.Boolean(
        compute="_t_payment_status_get", string=_("Fully paid"), store=True
    )
    unknown_date = fields.Boolean()
    ignore_invoice_creation = fields.Boolean()

    def action_reserve_force(self):
        waiting = self.move_lines.filtered(lambda l: l.state == "waiting")
        for move in waiting:
            if move.move_orig_ids:
                move.write(
                    {
                        "move_orig_ids": [(6, 0, [])],
                    }
                )
            else:
                if move.created_purchase_line_id.state in ("draft", "sent"):
                    move.created_purchase_line_id = False
        waiting.write({"procure_method": "make_to_stock"})
        self.action_assign()

    def _create_backorder(self):
        backorders = super(StockPicking, self)._create_backorder()
        backorders.write({"move_type": "one"})
        return backorders

    def write(self, vals):
        if "unknown_date" in vals and vals.get("unknown_date", False):
            vals["scheduled_date"] = datetime.now() + relativedelta(days=90)
        return super(StockPicking, self).write(vals)

    def latest_expected_skus(self):
        self.ensure_one()
        latest_date = self.move_lines.sorted(lambda m: m.date_expected, True)[
            :1
        ].date_expected
        return self.move_lines.filtered(
            lambda m: m.date_expected.date() == latest_date.date()
        ).mapped("product_id.default_code")

    delay_picking_id = fields.Many2one(
        comodel_name="stock.picking", compute="_get_delay_po"
    )
    delay_partner_id = fields.Many2one(
        comodel_name="res.partner", compute="_get_delay_po"
    )
    old_date_expected = fields.Datetime(
        string="Old Date", compute="_get_old_date_expected"
    )

    def _get_delay_po(self):
        for picking in self:
            delay_activity = picking.activity_ids.filtered(
                lambda a: "The scheduled date" in a.note
            ).sorted("create_date", True)[:1]
            picking_id = (
                delay_activity
                and re.findall(r'data-oe-id="(\d+)"', delay_activity.note)
                or []
            )
            if len(picking_id) == 1:
                picking_id = picking_id[0]
                picking.delay_picking_id = int(picking_id)
                picking.delay_partner_id = picking.delay_picking_id.partner_id.id
            else:
                picking.delay_picking_id = False
                picking.delay_partner_id = False

    @api.depends("move_lines.old_date_expected", "move_type")
    def _get_old_date_expected(self):
        for record in self:
            dates = [
                date for date in record.move_lines.mapped("old_date_expected") if date
            ]
            if dates:
                if record.move_type == "direct":
                    record.old_date_expected = min(dates)
                else:
                    record.old_date_expected = max(dates)
            else:
                record.old_date_expected = False

    def action_validate_create_backorder(self):
        self.ensure_one()
        res = self.button_validate()
        bo_model = "stock.backorder.confirmation"
        if isinstance(res, dict):
            if res.get("res_model", False) == bo_model:
                backorder_wiz_id = res.get("res_id")
                wiz = self.env[bo_model].browse(backorder_wiz_id)
                wiz.process()
            else:
                raise UserError("Backorder condition not met.")
        return {"result": True}

    def action_create_batch(self):
        pickings = self.move_ids_without_package.mapped(
            "origin_so_picking_ids"
        ).filtered(lambda sp: sp.t_delivery_allowed and sp.state == "assigned")
        if not pickings:
            return
        batch = self.env["stock.picking.batch"].create(
            {"state": "draft", "picking_ids": [(4, pid, 0) for pid in pickings.ids]}
        )

        return {
            "name": batch.name,
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "stock.picking.batch",
            "res_id": batch.id,
        }

    def action_mass_mail(self):
        composer_form_view_id = self.env.ref(
            "mail.email_compose_message_wizard_form"
        ).id
        template_id = (
            self.env["mail.template"]
            .search([("model_id.model", "=", self._name)], limit=1)
            .id
        )

        return {
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "mail.compose.message",
            "view_id": composer_form_view_id,
            "target": "new",
            "context": {
                "default_composition_mode": "mass_mail"
                if len(self.ids) > 1
                else "comment",
                "default_res_id": self.ids[0],
                "default_model": "stock.picking",
                "default_use_template": bool(template_id),
                "default_template_id": template_id,
                "active_ids": self.ids,
            },
        }

    @api.depends(
        "sale_id", "state", "sale_id.t_is_delivery_invoice_policy", "sale_id.t_is_paid"
    )
    def _t_delivery_allowed_get(self):
        for r in self:
            order = r.sale_id

            r.t_delivery_allowed = bool(
                order and (order.t_is_delivery_invoice_policy or r.t_payment_status)
            )

    @api.depends("origin")
    def _compute_t_invoice_ids_to_report(self):
        invoice_ids = self.env["account.move"].search(
            [
                ["invoice_origin", "in", self.mapped("origin")],
                ["state", "not in", ["draft", "cancel"]],
            ]
        )

        for r in self:
            r.t_invoice_ids_to_report = invoice_ids.filtered(
                lambda i: i.invoice_origin == r.origin
            )

    @api.depends("partner_id")
    def _get_t_partner_outside_eu(self):
        eu_group = self.env["ir.model.data"].get_object("base", "europe")
        eu_country_ids = eu_group.country_ids.ids
        for sp in self:
            sp.t_partner_outside_eu = sp.partner_id.country_id.id not in eu_country_ids

    def _search_t_partner_outside_eu(self, operator, value):
        eu_group = self.env["ir.model.data"].get_object("base", "europe")
        eu_country_ids = eu_group.country_ids.ids
        op = "in"
        if operator == "=":
            if value:
                op = "not in"
            else:
                op = "in"
        elif operator == "!=":
            if value:
                op = "in"
            else:
                op = "not in"
        else:
            raise Exception("Unhandled operator {}".format(operator))

        return [("partner_id.country_id.id", op, eu_country_ids)]

    @api.depends("sale_id", "sale_id.t_is_paid")
    def _t_payment_status_get(self):
        for r in self:
            order = r.sale_id
            r.t_payment_status = order and order.t_is_paid

    def action_done(self):
        rets = True
        # SO-44999 Create invoice for 'delivery' invoice policy
        for r in self:
            try:
                ret = super(StockPicking, r).action_done()
                rets = rets and ret
            except UserError as e:
                msg = "%s: %s" % (r.name, e.name)
                raise UserError(msg)
            except ValidationError as e:
                msg = "%s: %s" % (r.name, e.name)
                raise ValidationError(msg)
            if not r.sale_id:
                continue
            # only create invoice for Delivery operation, not reshipment, SO
            # Payment term delivery and all qty is delivered
            if (
                not r.ignore_invoice_creation
                and r.picking_type_code == "outgoing"
                and (
                    r.sale_id.t_invoice_policy == "delivery"
                    or r.sale_id.all_qty_delivered
                )
            ):
                r.sale_id._create_invoice()
                r.sale_id._send_invoice()
            # SO-45007 don't do auto invoices for purchase orders
            # elif r.purchase_id:
            #     if r.purchase_id.t_purchase_method == 'receive':
            #         r.purchase_id._create_invoice()

        return rets

    def fill_done_qtys(self):
        for r in self:
            for ml in r.move_ids_without_package:
                ml.quantity_done = ml.product_uom_qty

    def get_ups_attachments(self):
        """Find attachments that match the UPS label name."""
        return self.env["ir.attachment"].search(
            [
                ["name", "=like", "LabelUPS%pdf"],
                ["type", "=", "binary"],
                ["res_model", "=", "stock.picking"],
                ["res_id", "in", self.ids],
            ]
        )

    def get_merged_ups_labels(self):
        return merge_pdf(
            [codecs.decode(att.datas, "base64") for att in self.get_ups_attachments()]
        )

    def action_mail_send(self):
        """Opens a wizard to compose an email, with relevant mail template loaded by default"""
        self.ensure_one()
        self.partner_id.lang
        template = self.env["mail.template"].search(
            [("model", "=", self._name)], limit=1
        )
        # if template.lang:
        #     lang = template._render_template(template.lang, self._name, self.ids[0])
        ctx = {
            "default_model": self._name,
            "default_res_id": self.ids[0],
            "default_use_template": bool(template),
            "default_template_id": template.id,
            "default_composition_mode": "comment",
            "custom_layout": "mail.mail_notification_light",
            "force_email": True,
            "model_description": "Order",
        }
        return {
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "mail.compose.message",
            "views": [(False, "form")],
            "view_id": False,
            "target": "new",
            "context": ctx,
        }

    def get_invoice_date(self):
        return self.sale_id.invoice_ids.filtered(
            lambda i: i.invoice_payment_state != "paid"
        )[:1].invoice_date

    def generate_non_ups_labels(self):
        for r in self:
            if r.carrier_id.delivery_type == "ups":
                continue

            # don't regenerate a label if it exists already
            if r.get_non_ups_labels():
                continue
            # skip if there are sendcloud labels
            try:
                next(r.get_sendcloud_labels())
                continue
            except StopIteration:
                pass

            pdf, _ = self.env.ref("tameson_stock.t_delivery_addresses").render_qweb_pdf(
                [r.id]
            )
            attachments = [("DeliveryAddresses.pdf", pdf)]
            r.message_post(body="Delivery addresses", attachments=attachments)

    def get_non_ups_labels(self):
        """Find attachments that match the UPS label name."""
        query = [
            ["name", "=like", "DeliveryAddresses%pdf"],
            ["type", "=", "binary"],
            ["res_model", "=", "stock.picking"],
            ["res_id", "in", self.ids],
        ]

        return self.env["ir.attachment"].search(query)

    def get_sendcloud_labels(self):
        if not hasattr(self, "sendcloud_parcel_ids"):
            return False
        for r in self:
            for parcel_id in r.sendcloud_parcel_ids:
                if parcel_id.label:
                    yield parcel_id.label

    def get_merged_labels(self):
        ups_attachments = self.get_ups_attachments()
        non_ups = self.get_non_ups_labels()
        sendcloud_labels = self.get_sendcloud_labels()
        att_dict = {att.res_id: att for att in ups_attachments}
        att_dict.update({att.res_id: att for att in non_ups})

        return merge_pdf(
            itertools.chain(
                (codecs.decode(att_dict[sp_id].datas, "base64") for sp_id in self.ids),
                (codecs.decode(sl, "base64") for sl in sendcloud_labels),
            )
        )


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    def get_ups_image_attachments(self, format="png"):
        yield from self.picking_ids.get_ups_image_attachments(format=format)

    def print_batch_stock_picking_invoices(self):
        return self.env.ref("tameson_stock.batch_stock_picking_invoices").report_action(
            self
        )


class MailComposer(models.TransientModel):
    _inherit = "mail.compose.message"

    def onchange_template_id(self, template_id, composition_mode, model, res_id):
        SaleReport = self.env.ref("sale.action_report_saleorder")
        InvoiceReport = self.env.ref("account.account_invoices")
        PurchaseReport = self.env.ref("purchase.action_report_purchase_order")
        Attachment = self.env["ir.attachment"]

        Delay = self.env.ref("tameson_stock.tameson_picking_order_delay")
        NoPay = self.env.ref("tameson_stock.tameson_picking_no_payment_received")
        NoPayCancel = self.env.ref("tameson_stock.tameson_picking_no_payment_cancel")
        PurchaseDateUpdate = self.env.ref(
            "tameson_stock.tameson_po_delivery_date_update"
        )

        vals = super(MailComposer, self).onchange_template_id(
            template_id, composition_mode, model, res_id
        )
        result = False
        if template_id == Delay.id and composition_mode != "mass_mail":
            order = self.env[model].browse(res_id).sale_id
            if order:
                result, format = SaleReport.render_qweb_pdf([order.id])
                report_name = order.name + ".pdf"

        if (
            template_id in (NoPay.id, NoPayCancel.id)
            and composition_mode != "mass_mail"
        ):
            open_invoice = (
                self.env[model]
                .browse(res_id)
                .sale_id.invoice_ids.filtered(
                    lambda i: i.invoice_payment_state != "paid"
                )[:1]
            )
            if open_invoice:
                result, format = InvoiceReport.render_qweb_pdf([open_invoice.id])
                report_name = open_invoice.name.replace("/", "_") + ".pdf"

        if template_id == PurchaseDateUpdate.id and composition_mode != "mass_mail":
            purchase = self.env[model].browse(res_id).purchase_id
            if purchase:
                result, format = PurchaseReport.render_qweb_pdf([purchase.id])
                report_name = purchase.name + ".pdf"

        if result:
            result = base64.b64encode(result)
            attachment = Attachment.create(
                {
                    "name": report_name,
                    "datas": result,
                    "res_model": "mail.compose.message",
                    "res_id": 0,
                    "type": "binary",
                }
            )
            vals["value"]["attachment_ids"] = [(6, 0, attachment.ids)]

        return vals


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    t_aa_shipper_mapping = fields.Char(
        string="Active Ant Shipment Mapping",
    )


class ReturnPicking(models.TransientModel):
    _inherit = "stock.return.picking"

    @api.onchange("picking_id")
    def _onchange_picking_id(self):
        super()._onchange_picking_id()
        self.location_id = False

    def action_create_reship(self):
        warehouse = self.env["stock.warehouse"].search(
            [("lot_stock_id", "=", self.location_id.id)]
        )
        picking_type = self.env["stock.picking.type"].search(
            [("code", "=", "outgoing"), ("warehouse_id", "=", warehouse.id)], limit=1
        )
        new_picking = self.picking_id.copy(
            {
                "ignore_invoice_creation": True,
                "move_lines": [],
                "picking_type_id": picking_type.id,
                "state": "draft",
                "origin": _("Reship of %s") % self.picking_id.name,
                "location_id": self.location_id.id,
                "location_dest_id": self.picking_id.location_dest_id.id,
            }
        )
        for return_line in self.product_return_moves:
            if return_line.quantity:
                vals = self._prepare_move_default_values(return_line, new_picking)
                vals.update(
                    {
                        "location_id": self.location_id.id,
                        "location_dest_id": self.picking_id.location_dest_id.id,
                        "origin_returned_move_id": False,
                        "warehouse_id": warehouse.id,
                    }
                )
                vals.pop("procure_method")
                return_line.move_id.copy(vals)
        new_picking.action_confirm()
        new_picking.action_assign()
        ctx = dict(self.env.context)
        self.env[ctx["active_model"]].browse(ctx["active_id"]).write(
            {"picking_ids": [(4, new_picking.id, 0)]}
        )
        ctx.update(
            {
                "default_partner_id": self.picking_id.partner_id.id,
                "search_default_picking_type_id": picking_type.id,
                "search_default_draft": False,
                "search_default_assigned": False,
                "search_default_confirmed": False,
                "search_default_ready": False,
                "search_default_late": False,
                "search_default_available": False,
            }
        )
        return {
            "name": _("Returned Picking"),
            "view_mode": "form,tree,calendar",
            "res_model": "stock.picking",
            "res_id": new_picking.id,
            "type": "ir.actions.act_window",
            "context": ctx,
        }
