###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import api, fields, models


class Pricelist(models.Model):
    _inherit = "product.pricelist"

    rate_id = fields.Many2one(
        string="Fixed rate",
        comodel_name="res.currency.rate",
        ondelete="restrict",
        domain='[("currency_id","=",currency_id)]',
    )
    shipping_fee_factor = fields.Float(
        string="Shipping Fee Factor",
    )
    company_rate = fields.Float(related="rate_id.company_rate")


class PricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    base = fields.Selection(
        selection_add=[("tameson", "Tameson Pricing")],
        ondelete={"tameson": "set default"},
    )

    shipping_fee_factor = fields.Float(
        related="pricelist_id.shipping_fee_factor", readonly=False
    )
    is_usd_extra = fields.Boolean()

    def _compute_base_price(self, product, quantity, uom, date, target_currency):
        target_currency.ensure_one()
        rule_base = self.base or "list_price"
        if rule_base == "tameson":
            src_currency = product.currency_id
            if self.is_usd_extra and product.usd_extra_price_factor > 0:
                extra_usd = product.usd_extra_price_factor
            else:
                extra_usd = 1.0
            price = (product.list_price + product.extra_shipping_fee_usd) * extra_usd
            if src_currency != target_currency:
                price = src_currency._convert(
                    price, target_currency, self.env.company, date, round=False
                )
        else:
            price = super()._compute_base_price(
                product, quantity, uom, date, target_currency
            )
        return price

    def _compute_price(self, product, quantity, uom, date, currency=None):
        if self.pricelist_id.rate_id.name:
            date = self.pricelist_id.rate_id.name
        return super()._compute_price(product, quantity, uom, date, currency)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    usd_extra_price_factor = fields.Float(default=1.0)
    extra_shipping_fee_usd = fields.Float(compute="get_usd_pricelist_price", store=True)
    extra_shipping_fee_gbp = fields.Float(compute="get_gbp_pricelist_price", store=True)

    sale_price_usd = fields.Float(compute="get_usd_pricelist_price", store=True)
    sale_price_gbp = fields.Float(compute="get_gbp_pricelist_price", store=True)

    @api.depends(
        "t_height", "t_length", "t_width", "usd_extra_price_factor", "list_price"
    )
    def get_usd_pricelist_price(self):
        pricelist = self.env["product.pricelist"].browse(3)  # USD Pricelist
        prices = pricelist._compute_price_rule(self, 1)
        for product in self:
            volume = (product.t_height * product.t_length * product.t_width) / 5000000
            product.extra_shipping_fee_usd = pricelist.shipping_fee_factor * max(
                product.weight, volume
            )
            product.sale_price_usd = prices[product.id][0]

    @api.depends("t_height", "t_length", "t_width", "list_price")
    def get_gbp_pricelist_price(self):
        pricelist = self.env["product.pricelist"].browse(2)  # USD Pricelist
        prices = pricelist._compute_price_rule(self, 1)
        for product in self:
            volume = (product.t_height * product.t_length * product.t_width) / 5000000
            product.extra_shipping_fee_gbp = pricelist.shipping_fee_factor * max(
                product.weight, volume
            )
            product.sale_price_gbp = prices[product.id][0]
