import requests


class PimcoreRequest(object):
    def __init__(self, host, name, apikey, timeout=1200):
        self.api_url = "%s/pimcore-graphql-webservices/%s?apikey=%s" % (
            host,
            name,
            apikey,
        )
        self.timeout = timeout

    def execute(self, gql_query):
        result = requests.post(self.api_url, json={"query": gql_query})
        return result.json()["data"]


class GqlQueryBuilder(object):
    def __init__(self, root, subroot, node, filters=None):
        self.root = root
        self.subroot = subroot
        self.node = node
        self.filters = filters or []

    def get_query(self, params=""):
        params_list = ["published: false"]
        if self.filters:
            filter = 'filter: "{%s}"' % ",".join(self.filters)
            params_list.append(filter)
        if params:
            params_list.append(params)
        full_param = ", ".join(params_list)
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
        """ % {
            "root": self.root,
            "subroot": self.subroot,
            "node_string": "\n".join(
                ["%s: %s" % (key, val["field"]) for key, val in self.node.items()]
            ),
            "filter": full_param,
        }
        return node_string

    def parse_results(self, result):
        result_lists = []
        if isinstance(result, dict):
            result = [result]
        for data in result:
            result_lists += data.get(self.root, {}).get(self.subroot, [])
        return result_lists

    def filter_by_skus(self, skus):
        return self.get_query(
            'filter: "{\\"$or\\": [%s]}"'
            % ",".join(['{\\"sku\\": \\"%s\\"}' % sku for sku in skus])
        )
