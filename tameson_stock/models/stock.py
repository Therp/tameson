from datetime import datetime

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _name = "stock.picking"
    _inherit = ["stock.picking", "set.help.mixin"]

    t_delivery_allowed = fields.Boolean(
        compute="_t_delivery_allowed_get",
        string=_("Delivery allowed"),
        store=True,
        readonly=False,
    )
    t_partner_outside_eu = fields.Boolean(
        string=_("Out of EU"),
        compute="_get_t_partner_outside_eu",
        search="_search_t_partner_outside_eu",
    )
    t_payment_status = fields.Boolean(
        compute="_t_payment_status_get", string=_("Fully paid"), store=True
    )
    unknown_date = fields.Boolean()
    unknown_date_incoming = fields.Boolean()
    ignore_invoice_creation = fields.Boolean()
    aftership_tracking = fields.Char(string="Aftership ID")
    aftership_url = fields.Char(
        string="Aftership URL", compute="_compute_aftership_url", copy=False
    )

    @api.onchange("unknown_date_incoming")
    def _onchange_unknown_date_incoming(self):
        self.move_ids.update({"unknown_date_incoming": self.unknown_date_incoming})

    @api.depends("aftership_tracking")
    def _compute_aftership_url(self):
        for record in self:
            record.aftership_url = (
                "https://admin.aftership.com/shipments/%s" % record.aftership_tracking
            )

    def _compute_carrier_tracking_url(self):
        for picking in self.filtered(lambda l: l.aftership_tracking):
            if picking.aftership_tracking:
                picking.carrier_tracking_url = (
                    "https://track.tameson.com/%s" % picking.carrier_tracking_ref
                )
        super(
            StockPicking, self.filtered(lambda l: not l.aftership_tracking)
        )._compute_carrier_tracking_url()

    def action_reserve_force(self):
        waiting = self.move_ids.filtered(lambda l: l.state == "waiting")
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
        latest_line = self.move_ids.sorted(lambda m: m.date_expected, True)[:1]
        latest_date = latest_line.date_expected
        return self.move_ids.filtered(
            lambda m: m.date_expected.date() == latest_date.date()
        ).mapped("product_id.default_code")

    def action_validate_create_backorder(self):
        self.ensure_one()
        res = self.button_validate()
        bo_model = "stock.backorder.confirmation"
        if isinstance(res, dict) and res.get("res_model", False) == bo_model:
            wiz = self.env[bo_model].with_context(res["context"]).create({})
            wiz.process()
        else:
            raise ValidationError(str(res))
        return {"id": self.id, "state": self.state}

    @api.depends("sale_id", "state", "sale_id.payment_term_id", "sale_id.t_is_paid")
    def _t_delivery_allowed_get(self):
        for r in self:
            order = r.sale_id
            r.t_delivery_allowed = bool(
                order
                and (
                    order.payment_term_id.t_invoice_delivered_quantities
                    or r.t_payment_status
                )
            )

    @api.depends("partner_id")
    def _get_t_partner_outside_eu(self):
        eu_group = self.env.ref("base.europe")
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

    def fill_done_qtys(self):
        for r in self:
            for ml in r.move_ids:
                ml.quantity_done = ml.product_uom_qty


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    external_mapping = fields.Text(
        string="External Mapping Data",
    )
    t_aa_shipper_mapping = fields.Char(
        string="Active Ant Shipment Mapping",
    )


class ReturnPicking(models.TransientModel):
    _inherit = "stock.return.picking"

    @api.onchange("picking_id")
    def _onchange_picking_id(self):
        super()._onchange_picking_id()
        self.location_id = False
