from odoo import models


class MergePartnerAutomatic(models.TransientModel):
    _inherit = "base.partner.merge.automatic.wizard"

    def _merge(self, partner_ids, dst_partner=None, extra_checks=True):
        if self.env.user.has_group("sales_team.group_sale_manager"):
            extra_checks = False

        return super(MergePartnerAutomatic, self)._merge(
            partner_ids, dst_partner=dst_partner, extra_checks=extra_checks
        )
