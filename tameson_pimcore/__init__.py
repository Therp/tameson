from . import models

def add_pimcore_modification_date(cr, registry):
    import time
    from datetime import datetime
    from dateutil.relativedelta import relativedelta
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    unixtime = time.mktime((datetime.now() - relativedelta(days=5)).timetuple())
    env['product.template'].search([]).write({'modification_date': unixtime})