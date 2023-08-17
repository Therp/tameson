###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import _, fields, models


def get_selection_label(self, object, field_name, field_value):
    return _(
        dict(
            self.env[object].fields_get(allfields=[field_name])[field_name]["selection"]
        )[field_value]
    )


class ResPartner(models.Model):
    _inherit = "res.partner"

    def can_edit_vat(self):
        if not (self.vat or self.parent_id):
            return True
        else:
            return super(ResPartner, self).can_edit_vat()

    type_name = fields.Char(compute="_get_type_name")

    def _get_type_name(self):
        self.type_name = get_selection_label(self, "res.partner", "type", self.type)
