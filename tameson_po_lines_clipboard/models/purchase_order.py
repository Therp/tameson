from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    clipboard_text_handle = fields.Char(
        string="Products Quantity (Clipboard)",
        compute="_compute_clipboard_text_handle",
    )

    @api.depends('order_line.product_qty', 'order_line.product_id')
    def _compute_clipboard_text_handle(self):
        for po in self:
            text_val_to_clipboard = ""
            for po_line in po.order_line:
                supplier_rec = po_line.product_id.seller_ids.filtered(
                    lambda v: v.name == po.partner_id
                )
                if supplier_rec and supplier_rec[0].product_code:
                    product_code = supplier_rec[0].product_code
                else:
                    product_code = po_line.product_id.default_code
                qty = str(po_line.product_qty)
                text_val_to_clipboard = (
                    text_val_to_clipboard
                    + "{prod_qty}\t{prod_code}\n".format(
                        prod_qty=qty, prod_code=product_code
                    )
                )
            if text_val_to_clipboard:
                po.clipboard_text_handle = text_val_to_clipboard

    def tameson_po_copy_clipboard(self):
        pass
