from .. import mixins
from ..base import ShopifyResource


class Transactions(ShopifyResource, mixins.Metafields):
    _prefix_source = "/shopify_payments/balance/"
