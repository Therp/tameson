from .. import mixins
from ..base import ShopifyResource


class Policy(ShopifyResource, mixins.Metafields, mixins.Events):
    pass
