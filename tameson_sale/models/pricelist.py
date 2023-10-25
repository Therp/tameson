###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import fields, models


class Pricelist(models.Model):
    _inherit = "product.pricelist"

    rate_id = fields.Many2one(
        string="Fixed rate",
        comodel_name="res.currency.rate",
        ondelete="restrict",
        domain='[("currency_id","=",currency_id)]',
    )

    company_rate = fields.Float(related="rate_id.company_rate")


class PricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    base = fields.Selection(
        selection_add=[("tameson", "Tameson Pricing")],
        ondelete={"tameson": "set default"},
    )

    shipping_fee_factor = fields.Float(
        string="Shipping Fee Factor",
    )
    is_usd_extra = fields.Boolean()

    def _compute_base_price(self, product, quantity, uom, date, target_currency):
        target_currency.ensure_one()
        rule_base = self.base or "list_price"
        if rule_base == "tameson":
            src_currency = product.currency_id
            shipping_fee = 0
            if self.shipping_fee_factor > 0:
                volume = product.volume
                shipping_fee = self.shipping_fee_factor * max(product.weight, volume)
            extra_usd = 1.0 if not self.is_usd_extra else product.usd_extra_price_factor
            price = (product.list_price + shipping_fee) * extra_usd
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
    extra_shipping_fee_usd = fields.Float(string="Extra shipping fee USD", default=0.0)
    extra_shipping_fee_gbp = fields.Float(string="Extra shipping fee GBP", default=0.0)

    sale_price_usd = fields.Float(string="USD Price", compute="get_pricelist_price")
    sale_price_gbp = fields.Float(string="GBP Price", compute="get_pricelist_price")

    def get_pricelist_price(self):
        pricelist = self.env["product.pricelist"].browse(2)
        prices = pricelist._compute_price_rule(self, 1)
        for pt in self:
            pt.sale_price_usd = prices[pt.id][0]
            pt.sale_price_gbp = prices[pt.id][0]
