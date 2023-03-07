from ... import shopify
from .. import mixins
from ..base import ShopifyResource


class Blog(ShopifyResource, mixins.Metafields, mixins.Events):
    def articles(self):
        return shopify.Article.find(blog_id=self.id)
