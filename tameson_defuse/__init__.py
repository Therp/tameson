import odoo
from .defuse import *


cr = odoo.registry().cursor()
on_load(cr)
