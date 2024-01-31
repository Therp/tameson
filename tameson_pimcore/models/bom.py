###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import fields, models


class MrpBOM(models.Model):
    _inherit = "mrp.bom"

    bom_signature = fields.Char(index=True)

    def get_bom_signature(self):
        self.ensure_one()
        return ",".join(
            self.bom_line_ids.mapped(
                lambda l: "%s,%.0f" % (l.product_id.default_code, l.product_qty)
            )
        )
