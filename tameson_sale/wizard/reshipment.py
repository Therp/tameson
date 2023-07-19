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
                    "discount": 100,
                    "warehouse_id": self.env["stock.warehouse"].search([], limit=1).id,
                },
            )
            for line in order.order_line
        ]
        return res


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
