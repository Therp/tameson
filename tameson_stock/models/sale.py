from odoo import _, api, fields, models
from odoo.tools import float_compare

# function to include AA stock difference report in mail 'ODOO data to check'
# class SaleOrder(models.Model):
# _inherit = 'sale.order'

# def _get_sale_order_has_issues(self):
# res = super(SaleOrder, self)._get_sale_order_has_issues()
# aa_data = self.env['aa.stock'].get_data()
# if aa_data:
# res.append({
# 'name': 'AA Stock mismatch',
# 'header': ['Product ID', 'SKU', 'Product Name', 'AA Quantity', 'Odoo Quantity'],
# 'orders': aa_data
# })
# return res


def warehouse_data(env, warehouses, product_id):
    quant = env["stock.quant"]
    data = {}
    for warehouse in warehouses:
        if product_id:
            qty = quant._get_available_quantity(product_id, warehouse.lot_stock_id)
        else:
            qty = 0
        data["stock_%d" % warehouse.id] = qty
    return data


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    # need to add this so that the tooltip widget will have necessary data to
    # render the min qty field
    minimal_qty_available = fields.Float(
        related="product_id.product_tmpl_id.minimal_qty_available",
        string=_("Product min qty available"),
        readonly=True,
    )

    minimal_qty_available_stored = fields.Float(
        related="product_id.product_tmpl_id.minimal_qty_available_stored",
        string=_("Product min qty available stored"),
        readonly=True,
    )

    supplierinfo_name = fields.Char(
        related="product_id.supplierinfo_name", string="Supplier"
    )
    stock_1 = fields.Float(
        compute="_get_wh_stock", string="S-T", digits="Product Unit of Measure"
    )
    stock_2 = fields.Float(
        compute="_get_wh_stock", string="S-AA", digits="Product Unit of Measure"
    )

    def _get_wh_stock(self):
        warehouses = self.env["stock.warehouse"].search([])
        for line in self:
            line.update(warehouse_data(self.env, warehouses, line.product_id))

    @api.onchange("product_id")
    def _onchange_product_warehouse(self):
        if self.product_id.wh_id:
            self.warehouse_id = self.product_id.wh_id

    @api.onchange("product_uom_qty", "product_uom", "product_id")
    def _onchange_product_id_check_min_availability(self):
        if not self.product_id or not self.product_uom_qty or not self.product_uom:
            return {}
        if self.product_id.type == "product":
            precision = self.env["decimal.precision"].precision_get(
                "Product Unit of Measure"
            )
            if (
                float_compare(
                    self.product_id.minimal_qty_available,
                    self.product_uom_qty,
                    precision_digits=precision,
                )
                == -1
            ):
                warning_mess = {
                    "title": _("Not enough inventory!"),
                    "message": _(
                        "You plan to sell %.2f %s but the minimum qty available is %.2f %s !\nThe current stock on hand is %.2f %s."
                    )
                    % (
                        self.product_uom_qty,
                        self.product_uom.name,
                        self.product_id.minimal_qty_available,
                        self.product_id.uom_id.name,
                        self.product_id.qty_available,
                        self.product_id.uom_id.name,
                    ),
                }
                return {"warning": warning_mess}
        return {}
