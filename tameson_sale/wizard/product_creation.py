###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import fields, models


class ProductCreationWizard(models.TransientModel):
    _name = "product.creation.wizard"
    _description = "Product Creation Wizard"

    name = fields.Char(required=True)
    vendor_id = fields.Many2one(
        comodel_name="res.partner", ondelete="cascade", required=True
    )
    vendor_code = fields.Char(required=True)
    hs_code = fields.Char(string="HS Code", required=True)
    barcode = fields.Char(required=True)
    country_id = fields.Many2one(
        string="Country of origin",
        comodel_name="res.country",
        ondelete="restrict",
        required=True,
    )
    default_code = fields.Char(string="Internal reference", required=True)
    vendor_lead_days = fields.Integer(required=True)
    purchase_price = fields.Float(required=True)
    sale_price = fields.Float(required=True)
    categ_id = fields.Many2one(
        string="Category",
        comodel_name="product.category",
        ondelete="cascade",
        required=True,
        default=lambda self: self.env.ref("product.category-custom-products").id,
    )

    _sql_constraints = [
        (
            "check_sale_purchase_price",
            "CHECK((purchase_price * 1.1) <= sale_price)",
            "Sale price must be higher than 1.1 times of the purchase price.",
        )
    ]

    def action_create(self):
        vals = {
            "name": self.name,
            "type": "product",
            "categ_id": self.categ_id.id,
            "standard_price": self.purchase_price,
            "list_price": self.sale_price,
            "default_code": self.default_code,
            "hs_code": self.hs_code,
            "barcode": self.barcode,
            "sticker_barcode": self.barcode,
            "intrastat_origin_country_id": self.country_id.id,
            "seller_ids": [
                (
                    0,
                    0,
                    {
                        "name": self.vendor_id.id,
                        "price": self.purchase_price,
                        "product_code": self.vendor_code,
                        "delay": self.vendor_lead_days,
                    },
                )
            ],
        }
        product = self.env["product.template"].create(vals)
        if (
            self._context.get("active_model", "") == "sale.order"
            and "active_id" in self._context
        ):
            sale = self.env["sale.order"].browse(self._context.get("active_id"))
            sale.write(
                {"order_line": [(0, 0, {"product_id": product.product_variant_id.id})]}
            )
            sale.onchange_partner_shipping_id()
            sale.recompute()
            sale._compute_tax_id()
            for line in sale.order_line:
                line._onchange_product_id_set_customer_lead()
        return {"type": "ir.actions.act_window_close"}
