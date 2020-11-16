# -*- coding: utf-8 -*-
"""
This script expects to be run on a buildout
"""
import argparse
import logging
import sys

# Flake8 raises F821 and is correctly signaling that session is not defined.
# flake8 does not know this should be called from python-odoo where we \
# already have session so we are silencing the message with # noqa comments

logging.basicConfig()
logger = logging.getLogger(__file__)  # pylint: disable=invalid-name
if 'session' not in locals():
    logger.error('Run me with python_odoo from a buildout!')
    sys.exit(1)

parser = argparse.ArgumentParser(  # pylint: disable=invalid-name
    description='Assign the correct accounting sale journal to clients')
parser.add_argument(  # pylint: disable=invalid-name
    'db', help='The name of your migrated v9 database')
args = parser.parse_args()   # pylint: disable=invalid-name
session.open(args.db)  # noqa: F821,E501  # pylint: disable=invalid-name,undefined-variable
cr = session.cr  # noqa: F821,E501  # pylint: disable=invalid-name,undefined-variable


# get all root warehouses. the parent location is badly named 'location_id'
# physical locations: stock.stock_location_locations

env = session.env  # noqa: F821,E501  # pylint: disable=invalid-name,undefined-variable

products = env['product.product'].search([])

product_discrepancies = []
for product in products:
    if product.minimal_qty_available != product.minimal_qty_available_stored:
        product_discrepancies.append((product.id, product.name))
print('product discrepancies {0}'.format(product_discrepancies))
print('number of product discrepancies {0}'.format(len(product_discrepancies)))


tmpls = env['product.template'].search([])
tmpl_discrepancies = []
for tmpl in tmpls:
    if tmpl.minimal_qty_available != tmpl.minimal_qty_available_stored:
        tmpl_discrepancies.append((tmpl.id, tmpl.name))
print('product discrepancies {0}'.format(tmpl_discrepancies))
print('number of product discrepancies {0}'.format(len(tmpl_discrepancies)))

