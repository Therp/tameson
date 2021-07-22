
# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
import csv
import tempfile
import paramiko

class StockMove(models.Model):
    _inherit = 'stock.move'
    
    def write(self, vals):
        propagated_date_field = False
        if vals.get('date_expected'):
            propagated_date_field = 'date_expected'
        elif vals.get('state', '') == 'done' and vals.get('date'):
            propagated_date_field = 'date'
        new_date = fields.Datetime.to_datetime(vals.get(propagated_date_field))
        res = super(StockMove, self).write(vals)
        ## Compare new date on Incoming operation with SO delivery/expected date
        ## Dismiss exception posted on Picking if not later than SO delivery/expected date + propagate_date_minimum_delta
        ## also dismiss manual date change exception if any
        if propagated_date_field:
            for move in self.mapped('move_dest_ids'):
                auto_activity = move.picking_id.activity_ids.filtered(lambda a: a.automated and 'The scheduled date has been automatically updated due to a delay on' in a.note)
                order_date = (move.picking_id.sale_id.commitment_date or move.picking_id.sale_id.expected_date) + relativedelta(days=self[:1].propagate_date_minimum_delta)
                if auto_activity and new_date <= order_date:
                    auto_activity.action_feedback(feedback="Scheduled on earlier date.")
                manu_activity = move.picking_id.activity_ids.filtered(lambda a: a.automated and 'The scheduled date should be updated due to a delay on' in a.note)
                if manu_activity:
                    manu_activity.action_feedback(feedback="Scheduled on earlier date.")
        ## end
        return res


    ## parameters
    ## hours: number of hours to check for last stock operation
    ## filename: output sftp filename
    ## host: sftp host
    ## port: sftp port
    ## username: sftp username
    ## password: sftp password
    def product_stock_export(self, hours=1, filename='stock-presta.csv', **kwargs):
        date_filter  = fields.Datetime.now() - relativedelta(hours=hours)
        header = ["quantity", "SKU"]
        products = self.search([('date','>=',date_filter), ('state','=','done')]).mapped('product_id')
        bom_products = self.env['mrp.bom.line'].search([('product_id','in',products.ids)]).mapped('bom_id').mapped('product_tmpl_id')
        fp = tempfile.NamedTemporaryFile(mode='w', encoding='UTF8')
        writer = csv.writer(fp)
        writer.writerow(header)
        writer.writerows((products.mapped('product_tmpl_id') + bom_products).mapped(lambda p: [p.minimal_qty_available, p.default_code]))
        fp.flush()
        host = kwargs.get("host", False) or "ns3.tameson.com"
        port = kwargs.get("port", False) or 22
        transport = paramiko.Transport((host, port))
        password = kwargs.get("password", False) or "4sK2buewXkNl"
        username = kwargs.get("username", False) or "sync_tameson.com"
        transport.connect(username = username, password = password)
        sftp = paramiko.SFTPClient.from_transport(transport)
        sftp.put(fp.name, filename)
        fp.close()
        sftp.close()
        transport.close()
