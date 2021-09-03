from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
from gql.transport.requests import log as req_logger
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.aiohttp import log as aio_logger
import asyncio
import logging
aio_logger.setLevel(logging.WARNING)
req_logger.setLevel(logging.WARNING)


class PimcoreRequest(object):
    def __init__(self, host, name, apikey, timeout=1200):
        self.api_url = "%s/pimcore-graphql-webservices/%s?apikey=%s" % (host, name, apikey)
        self.timeout = timeout
        self.async_transport = AIOHTTPTransport(url=self.api_url)
        self.transport = RequestsHTTPTransport(url=self.api_url)
        self.sync_client = Client(transport=self.transport, fetch_schema_from_transport=False, execute_timeout=timeout)

    def execute(self, gql_query):
        result = self.sync_client.execute(gql_query)
        return result

    def execute_async(self, queryb, start, quantity, batch_size):
        return asyncio.run(self.execute_async_main(queryb, start, quantity, batch_size))

    async def execute_async_main(self, queryb, start, quantity, batch_size):
        filters = (queryb.get_query("first: %d, after: %d" % (batch_size, after)) for after in range(start, start + quantity, batch_size))
        async with Client(transport=self.async_transport, fetch_schema_from_transport=False, execute_timeout=1200) as session:
            results = await asyncio.gather(*(asyncio.create_task(session.execute(f)) for f in filters))
        return results


class GqlQueryBuilder(object):
    def __init__(self, root, subroot, node, filters=[]):
        self.root = root
        self.subroot = subroot
        self.node = node
        self.filters = filters

    def get_query(self, params=""):
        params_list = []
        if self.filters:
            filter = 'filter: "{%s}"' % ','.join(self.filters)
            params_list.append(filter)
        if params:
            params_list.append(params)
        full_param = ', '.join(params_list)
        node_string = """
            {
                %(root)s (%(filter)s) {
                    %(subroot)s {
                        node {
                            %(node_string)s
                        }
                    }
                }
            }
        """ % {'root': self.root,
                'subroot': self.subroot,
                'node_string': "\n".join(["%s: %s" % (key, val['field']) for key, val in self.node.items()]),
                'filter': full_param}
        return gql(node_string)

    def parse_results(self, result):
        result_lists = []
        if isinstance(result, dict):
            result = [result]
        for data in result:
            result_lists += data.get(self.root, {}).get(self.subroot, [])
        return result_lists
    
    def filter_by_skus(self, skus):
        return self.get_query('filter: "{\\"$or\\": [%s]}"' % ','.join(['{\\"sku\\": \\"%s\\"}' % sku for sku in skus]))
