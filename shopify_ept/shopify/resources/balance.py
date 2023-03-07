from .. import mixins
from ..base import ShopifyResource


class Balance(ShopifyResource, mixins.Metafields):
    _prefix_source = "/shopify_payments/"
    _singular = _plural = "balance"
