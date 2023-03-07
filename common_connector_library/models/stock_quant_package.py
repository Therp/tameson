from odoo import fields, models


class StockQuantPackage(models.Model):
    _inherit = "stock.quant.package"

    tracking_no = fields.Char(
        "Additional Reference", help="This Field Is Used For The Store Tracking No"
    )
