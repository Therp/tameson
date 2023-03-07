from .. import mixins
from ..base import ShopifyResource


class Disputes(ShopifyResource, mixins.Metafields):
    _prefix_source = "/shopify_payments/"
