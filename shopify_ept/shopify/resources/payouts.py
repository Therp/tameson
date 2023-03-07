from .. import mixins
from ..base import ShopifyResource


class Payouts(ShopifyResource, mixins.Metafields):
    _prefix_source = "/shopify_payments/"
