from .. import mixins
from ..base import ShopifyResource


class Page(ShopifyResource, mixins.Metafields, mixins.Events):
    pass
