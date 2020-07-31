import json


def get_locator():
    from odoo.addons import tameson_delivery_ups

    return tameson_delivery_ups.models.ups_request.UPSLocator(
        'tameson',
        'R3sistor70',
        '30F932',
        '8D162691485C6898',
        False
    )


def get_candidate_data(locator):
    sample = locator.SAMPLE_US_LOCATION
    return locator.address_key_format_to_locate_data(sample)


#uk_data = {
#    'street': '30 The Grampians',
#    'political-division-1': 'England',
#    'political-division-2': 'London',
#    'political-division-3': 'London',
#    'postal-code': 'W6 7LN',
#    'country-code': 'GB',
#}

#print "Data"
#pprint.pprint(search_data)


def find_working_access_point(locator, results):
    #res = locator.get_access_point('U23025483')
    iids = [r['AccessPointInformation']['PublicAccessPointID'] for r in results]
    print("Access point ids:", iids)

    for iid in iids:
        res = locator.get_access_point(iid)
        if res['status'] != 'error':
            return iid, res
        else:
            print(res['error'])
    #print 'No access point found!'


def main():
    locator = get_locator()

    candidate_data = get_candidate_data(locator)
    #candidate_data = {
    #    'latitude': candidate_data['latitude'],
    #    'longitude': candidate_data['longitude'],
    #}
    # candidate_data = {
    #     'street': '',
    #     'postal-code': '',
    #     'political-division-1': candidate_data['political-division-1'],
    #     'political-division-2': candidate_data['political-division-2'],
    #     'country-code': candidate_data['country-code'],
    #     'search-radius': '200',
    # }
    candidate_data = {
        'street': '',
        'postal-code': '',
        #'political-division-1': '',
        'political-division-2': 'Neuss',
        'country-code': 'DE',
        'search-radius': '200',
    }

    print(("candidate-data", candidate_data))

    s_res = locator.locate_access_point(data=candidate_data)

    if s_res['status'] == 'error':
        print((json.dumps(s_res['error'], indent=2)))
        print((json.dumps(json.loads(s_res['request']), indent=2)))

    #print "Response"
    #pprint.pprint(s_res['results'])
    #pprint.pprint(s_res['candidates'])

    iid = None
    results = s_res['results']
    if not results:
        print('No results')
        if not s_res['candidates']:
            print('No candidates')
        else:
            print("No results found, trying candidates")
            for candidate in s_res['candidates']:
                print("Trying candidate", candidate['AddressKeyFormat']['CosigneeName'])
                s_res = locator.locate_access_point_candidate(candidate)
                results = s_res['results']

    iid = find_working_access_point(locator, results)

    if not iid:
        print("No usable access point found")
    else:
        iid, res = iid
        print("Found", iid)
        print(locator.address_key_format_to_locate_data(res['result']))
