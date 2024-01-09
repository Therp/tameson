###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import api, fields, models


class ReshipmentWizard(models.TransientModel):
    _name = "reshipment.wizard"
    _description = "Reshipment Wizard"

    line_ids = fields.One2many(
        comodel_name="reshipment.wizard.line",
        inverse_name="wizard_id",
    )

    @api.model
    def default_get(self, fields):
        res = super(ReshipmentWizard, self).default_get(fields)
        order = self.env["sale.order"].browse(self.env.context["active_ids"])
        res["line_ids"] = [
            (
                0,
                0,
                {
                    "product_id": line.product_id.id,
                    "quantity": line.product_uom_qty,
                    "discount": 0,
                    "warehouse_id": self.env["stock.warehouse"].search([], limit=1).id,
                },
            )
            for line in order.order_line.filtered(
                lambda line: line.product_id.type == "product"
            )
        ]
        return res

    def action_add(self):
        order = self.env["sale.order"].browse(self.env.context["active_ids"])
        if not order.workflow_process_id:
            payment_term = (
                order.payment_term_id or order.partner_id.property_payment_term_id
            )
            order.workflow_process_id = payment_term.workflow_process_id
        order.write(
            {
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": line.product_id.id,
                            "discount": line.discount,
                            "warehouse_id": line.warehouse_id.id,
                            "product_uom_qty": line.quantity,
                        },
                    )
                    for line in self.line_ids
                ]
            }
        )
        self.env["automatic.workflow.job"].sudo().run_with_workflow(
            order.workflow_process_id
        )


class ReshipmentWizardLine(models.TransientModel):
    _name = "reshipment.wizard.line"
    _description = "Reshipment Wizard Line"

    wizard_id = fields.Many2one(
        comodel_name="reshipment.wizard",
        ondelete="restrict",
    )

    product_id = fields.Many2one(
        comodel_name="product.product",
        ondelete="restrict",
    )

    quantity = fields.Float()

    discount = fields.Float()

    warehouse_id = fields.Many2one(
        string="Source",
        comodel_name="stock.warehouse",
        ondelete="restrict",
    )
