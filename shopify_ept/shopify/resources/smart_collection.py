from ... import shopify
from .. import mixins
from ..base import ShopifyResource


class SmartCollection(ShopifyResource, mixins.Metafields, mixins.Events):
    def products(self):
        return shopify.Product.find(collection_id=self.id)
