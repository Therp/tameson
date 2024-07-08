import json

from odoo import _, api, fields, models
from odoo.tools import float_compare


class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = ["sale.order", "set.help.mixin"]

    t_is_paid = fields.Boolean(
        compute="_get_t_is_paid", string=_("Is order paid?"), readonly=True, store=True
    )
    all_qty_delivered = fields.Boolean(
        compute="_compute_all_qty_delivered",
        string="All quantities delivered",
        store=True,
    )

    origin = fields.Char(index=True)
    any_non_returnable = fields.Boolean(compute="_check_any_non_returnable")
    any_use_up = fields.Boolean(compute="_check_any_non_returnable")
    non_returnable_skus = fields.Char(compute="_check_any_non_returnable")
    uu_skus = fields.Char(compute="_check_any_non_returnable")
    uu_replacement_skus = fields.Char(compute="_check_any_non_returnable")
    uu_replacement_skus_en = fields.Char(compute="_check_any_non_returnable")
    weight_over_25 = fields.Char(compute="_check_any_non_returnable")
    customer_child_count = fields.Integer(compute="get_customer_child_count")
    customer_ref_warning = fields.Boolean(compute="get_customer_ref_warning")
    expected_date_warning = fields.Boolean(compute="get_expected_date_warning")
    payment_term_warning = fields.Boolean(compute="get_payment_term_warning")
    ecommerce_status_updated = fields.Boolean(default=False)
    origin = fields.Char(copy=False, index=True)
    workflow_process_id = fields.Many2one(copy=False)
    user_id = fields.Many2one(copy=False)

    arrival_min = fields.Integer()
    arrival_max = fields.Integer()
    shipped_days = fields.Integer()

    manager_user = fields.Boolean(compute="get_manager_user")

    _sql_constraints = [
        (
            "sale_order_origin_uniq",
            "unique (origin)",
            "Source document of Sale Order must be unique for each order!",
        )
    ]

    def copy(self):
        res = super().copy()
        res._onchange_payment_term_workflow()
        return res

    @api.depends_context("uid")
    def get_manager_user(self):
        for record in self:
            record.manager_user = self.user_has_groups("sales_team.group_sale_manager")

    @api.depends("partner_id", "payment_term_id")
    def get_payment_term_warning(self):
        for record in self:
            record.payment_term_warning = self.partner_id and (
                self.payment_term_id != self.partner_id.property_payment_term_id
                or self.payment_term_id.id == 52
            )

    @api.depends("partner_id.is_company", "client_order_ref")
    def get_customer_ref_warning(self):
        for record in self:
            record.customer_ref_warning = not (
                self.client_order_ref or not self.partner_id.is_company
            )

    @api.depends("order_line.customer_lead")
    def get_expected_date_warning(self):
        for record in self:
            record.expected_date_warning = (
                max(record.mapped("order_line.customer_lead") or [0]) > 4
            )

    @api.depends("partner_id")
    def get_customer_child_count(self):
        for record in self:
            record.customer_child_count = len(record.partner_id.child_ids)

    def _send_order_confirmation_mail(self):
        if self.env.context.get("skip_confirmation_email", False):
            return
        return super()._send_order_confirmation_mail()

    @api.depends(
        "order_line.product_id.non_returnable",
        "order_line.product_id.t_use_up",
        "order_line.product_id.weight",
        "partner_id",
    )
    def _check_any_non_returnable(self):
        self.env.context = dict(self.env.context, lang=self.partner_id.lang or "en_US")
        for record in self:
            nr_products = self.order_line.mapped("product_id").filtered(
                lambda p: p.non_returnable
            )
            record.any_non_returnable = bool(nr_products)
            record.non_returnable_skus = ",".join(
                nr_products.mapped("default_code") or []
            )

            uu_products = self.order_line.mapped("product_id").filtered(
                lambda p: p.t_use_up
            )
            uur_products = self.order_line.mapped("product_id").filtered(
                lambda p: p.t_use_up_replacement_sku
            )
            record.any_use_up = bool(uu_products)
            record.uu_skus = ",".join(uu_products.mapped("default_code"))
            add_text = _(" will be replaced by ")
            record.uu_replacement_skus = ", ".join(
                uur_products.mapped(
                    lambda p: p
                    and p.default_code + add_text + p.t_use_up_replacement_sku
                )
            )
            record.uu_replacement_skus_en = ", ".join(
                uur_products.mapped(
                    lambda p: p
                    and p.default_code
                    + " will be replaced by "
                    + p.t_use_up_replacement_sku
                )
            )
            record.weight_over_25 = (
                sum(
                    self.order_line.mapped(
                        lambda l: l.product_id.weight * l.product_uom_qty
                    )
                )
                >= 25.0
            )

    @api.onchange("any_non_returnable", "any_use_up", "uu_replacement_skus")
    def _onchange_warning(self):
        self.env.context = dict(self.env.context, lang=self.partner_id.lang or "en_US")
        exist_note = self.note or ""
        note = ""
        if self.any_non_returnable:
            note = note + (
                _("Warning: We kindly inform you that this item ")
                + self.non_returnable_skus
                + _(" cannot be returned. This is manufactured on demand for you.")
                + "<br />"
            )
        if self.any_use_up:
            note = (
                note
                + (_("Warning: ") + self.uu_skus + _(" is being discontinued."))
                + "<br />"
            )
        if self.uu_replacement_skus:
            note = note + (_("Warning: ") + self.uu_replacement_skus) + "<br />"
        if note:
            self.note = exist_note + note

    @api.depends("order_line.qty_delivered", "order_line.product_uom_qty")
    def _compute_all_qty_delivered(self):
        precision = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )
        for order in self:
            order.all_qty_delivered = all(
                line.product_id.type not in ("product", "consu")
                or float_compare(
                    line.qty_delivered, line.product_uom_qty, precision_digits=precision
                )
                == 0
                for line in order.order_line
            )

    def action_create_product(self):
        action = self.env.ref("tameson_sale.action_product_creation_wizard_act_window")
        return action.sudo().read()[0]

    @api.depends(
        "invoice_ids",
        "order_line",
        "order_line.product_uom_qty",
        "order_line.qty_invoiced",
        "invoice_ids.payment_state",
    )
    def _get_t_is_paid(self):
        for r in self:
            full_invoiced = all(
                r.order_line.mapped(lambda l: l.product_uom_qty <= l.qty_invoiced)
            )
            all_invoice_paid = all(
                r.invoice_ids.mapped(
                    lambda i: i.payment_state in ("paid", "in_payment", "reversed")
                )
            )
            r.t_is_paid = full_invoiced and all_invoice_paid

    def action_confirm_ecommerce(self):
        return self.with_context(bypass_risk=True).action_confirm()

    def action_confirm(self):
        over_amount = float(
            self.env["ir.config_parameter"].sudo().get_param("shipping_over_amount", 0)
        )
        if over_amount and self.amount_total >= over_amount:
            data = (
                self.env["ir.config_parameter"]
                .sudo()
                .get_param("shipping_over_data", "")
                .split(",")
            )
            data_dic = {}
            for country, shipping in zip(data[0::2], data[1::2]):
                data_dic[country] = shipping
            ccode = self.partner_shipping_id.country_id.code
            if ccode in data_dic:
                shipping = self.env["delivery.carrier"].search(
                    [("name", "ilike", data_dic[ccode])], limit=1
                )
                if shipping:
                    if self.carrier_id:
                        self.carrier_id = shipping
                    else:
                        self.set_delivery_line(shipping, 0)
        ret = super(SaleOrder, self).action_confirm()
        from_ui = self.env.context.get("from_ui", False)
        if from_ui and self.workflow_process_id:
            self.env["automatic.workflow.job"].sudo().run_with_workflow(
                self.workflow_process_id
            )
        return ret

    def get_skus_json(self):
        products = self.mapped("order_line.product_id.product_tmpl_id").filtered(
            lambda pt: pt.type == "product"
        )
        return json.dumps(products.mapped(lambda p: [p.default_code, p.display_name]))

    def action_add_express_shipping(self):
        carriers = self.env["delivery.carrier"].search(
            [("name", "=", "Express shipment")]
        )
        carriers = carriers.available_carriers(self.partner_shipping_id)
        if carriers:
            wizard = self.env["choose.delivery.carrier"].create(
                {"carrier_id": carriers[:1].id, "order_id": self.id}
            )
            wizard.update_price()
            wizard.button_confirm()

    @api.onchange("payment_term_id")
    def _onchange_payment_term_workflow(self):
        self.workflow_process_id = self.payment_term_id.workflow_process_id

    @api.onchange("partner_id")
    def onchange_partner_note(self):
        exist_note = self.note or ""
        country_note = self.partner_id.country_id.customer_note
        if country_note:
            self.note = exist_note + country_note

    def action_adjust_channable_tax(self):
        for line in self.order_line:
            ratio = 1 + (sum(line.tax_id.mapped("amount")) / 100.00)
            line.price_unit = line.price_unit / ratio

    def action_ecommerce_import(self):
        self.ensure_one()
        for line in self.order_line:
            line.onchange_product_id_set_customer_lead()
        self.onchange_partner_note()
        self._onchange_warning()

    def _find_mail_template(self):
        Tmpl = self.env["mail.template"]
        if self.state in ("draft", "sent"):
            name = "Tameson - Quotation"
        else:
            if self.payment_term_id.t_invoice_delivered_quantities:
                name = "Tameson - Sales order confirmation (payment term)"
            else:
                name = "Tameson - Sales order confirmation (pre pay)"
        return Tmpl.search([("name", "ilike", name)], limit=1)


class WorkflowJob(models.Model):
    _inherit = "automatic.workflow.job"

    def _do_create_invoice(self, sale, domain_filter):
        res = super()._do_create_invoice(sale, domain_filter)
        sale.write({"workflow_process_id": False})
        return res


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    supplierinfo_name = fields.Char(
        related="product_id.supplierinfo_name", string="Supplier"
    )

    qty_order_data = fields.Text(
        string="Qty to Order",
        compute="get_current_max_data",
    )

    @api.depends("product_id.max_qty_order_array")
    def get_current_max_data(self):
        for record in self:
            data = record.product_id.max_qty_order_array
            if record.product_id.detailed_type == "product" and data:
                data = json.loads(data)
                record.qty_order_data = "\n".join(
                    ["%dD: %d" % (i["lead_time"], i["max_qty"]) for i in data]
                )
            else:
                record.qty_order_data = ""

    @api.onchange("product_id", "product_uom_qty")
    def onchange_product_id_set_customer_lead(self):
        data = self.product_id.max_qty_order_array
        data = json.loads(data or "[]")
        if self.product_id.detailed_type != "product" or not data:
            self.customer_lead = 0
            return
        lead_time = data[-1]["lead_time"]
        for values in data:
            if self.product_uom_qty <= values["max_qty"]:
                lead_time = values["lead_time"]
                break
        self.customer_lead = lead_time
