###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import api, fields, models


class ProductCatregory(models.Model):
    _inherit = "product.category"

    complete_name = fields.Char(index=True)


class ProductPublicCatregory(models.Model):
    _inherit = "product.public.category"

    complete_name = fields.Char(
        "Complete Name", compute="_compute_complete_name", store=True, index=True
    )

    @api.depends("name", "parent_id.complete_name")
    def _compute_complete_name(self):
        for category in self:
            if category.parent_id:
                category.complete_name = "%s / %s" % (
                    category.parent_id.complete_name,
                    category.name,
                )
            else:
                category.complete_name = category.name
