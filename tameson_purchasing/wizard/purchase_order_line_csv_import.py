import csv
import io
import base64
import odoo
from odoo import api, fields, models, modules, tools, exceptions, registry, SUPERUSER_ID, _
from odoo.exceptions import UserError


class PurchaseOrderLineCsvImportImport(models.TransientModel):
    _name = 'purchase.orderline.csv.import'
    _description = 'PO Import Wizard'
    _rec_name = 'filename'

    def _get_default_purchase_order(self):
        purchase_order_id = self.env['purchase.order'].browse(self._context.get('active_id', False))
        if purchase_order_id and purchase_order_id.state != 'draft':
            raise UserError(_('Only orders in draft state can be used with the .csv import!'))
        return self._context.get('active_id', False)

    purchase_order_id = fields.Many2one('purchase.order', required=True, default=_get_default_purchase_order)
    csv_file = fields.Binary(string='File', help='Must be in .csv format.')
    filename = fields.Char(string='Filename')
    line_ids = fields.One2many('purchase.orderline.csv.import.line', 'wizard_id', string='Lines to import')
    state = fields.Selection(string="State", selection=[('draft', 'Draft'), ('loaded', 'Loaded'), ('imported', 'Imported')], default='draft')

    @api.onchange('csv_file')
    def action_load(self):
        if self.filename and self.filename[-3:] == 'csv':
            lines = []
            if self.line_ids:
                self.line_ids = False

            decoded_datas = base64.decodebytes(self.csv_file)
            f = io.TextIOWrapper(io.BytesIO(decoded_datas), encoding='utf-8')
            reader = csv.reader(f, delimiter=',', quotechar='"')
            data = [row for row in reader]
            rowno = 0
            product_product_obj = self.env['product.product']
            for line in data:
                rowno = rowno + 1
                qty = line[0] or 1
                sku = line[1]
                product = product_product_obj.search([('default_code', '=', sku)], limit=1) or False
                if product:
                    product_id = product.id
                else:
                    raise UserError(_('Line #' + str(rowno) + ' does not have a valid product SKU: ' + sku + ', please correct it!'))
                unit_price = product.list_price

                lines.append((0, 0, {
                    'product_id': product_id,
                    'quantity': qty,
                    'unit_price': unit_price,
                }))
            if lines:
                self.line_ids = lines
                self.state = 'loaded'
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
        elif self.filename:
            raise UserError(_('Please upload a .csv file for import!'))

    def action_import(self):
        self.action_load()
        if self.purchase_order_id and self.purchase_order_id.state != 'draft':
            raise UserError(_('Only orders in draft state can be used with the .csv import!'))
        if self.line_ids:
            line_count = 0
            order_lines = []
            for line in self.line_ids:
                order_lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.product_id.name,
                    'date_planned': fields.Datetime.now(),
                    'product_uom': line.product_id.uom_po_id and line.product_id.uom_po_id.id or line.product_id.uom_id.id,
                    'product_qty': line.quantity,
                    'price_unit': line.unit_price
                }))
                line_count = line_count + 1
            try:
                self.purchase_order_id.write({
                    'order_line': order_lines
                })
            except Exception as e:
                raise UserError(_('Purchase order lines were not imported, error: \n\n' + str(e)))

            self.line_ids = False
            self.state = 'imported'

            action = self.env.ref('purchase.purchase_rfq').read()[0]
            if action:
                action['views'] = [(self.env.ref('purchase.purchase_order_form').id, 'form')]
                action['res_id'] = self.purchase_order_id.id
            else:
                action = {'type': 'ir.actions.act_window_close'}
            return action
        else:
            raise UserError(_('Nothing to import!'))


class PurchaseOrderLineImportImportLine(models.TransientModel):
    _name = 'purchase.orderline.csv.import.line'
    _description = 'PO Import Lines'

    wizard_id = fields.Many2one('purchase.orderline.csv.import', string='Wizard')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    quantity = fields.Float('Quantity')
    unit_price = fields.Float('Unit Price', digits='Product Price')
