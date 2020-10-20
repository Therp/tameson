from odoo import api, fields, models, _
from odoo.exceptions import Warning, ValidationError
from odoo.addons.web.controllers.main import Export, CSVExport, ExcelExport
from odoo.tools import safe_eval
from odoo.tools.profiler import profile
import ast
import base64
import io
import logging
import time
import itertools
import ftplib

try:
    import paramiko
except Exception as e:
    raise ImportError('Dependency failure: "sftp" requires python library "paramiko": %s.' % str(e))

EXPORT_FORMATS = [
    ('csv', '.csv format'),
    ('xlsx', '.xlsx format'),
]
EXPORT_STATES = [
    ('draft', 'Draft'),
    ('sent', 'Sent'),
    ('failed', 'Failed'),
    ('no_data', 'No Data'),
]
_logger = logging.getLogger(__name__)


class CustomExporter(models.Model):
    _name = "custom.exporter"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Custom Export'

    name = fields.Char(required=True, string='Name')
    export_format = fields.Selection(
        string="File Format",
        selection=EXPORT_FORMATS,
        default='csv',
        required=True
    )
    export_filename_prefix = fields.Char(
        required=True, string='Filename Prefix')
    fixed_filename = fields.Boolean(help="""
        Check if this exporter will always use the same file name and overwrite
        it on every run. If unchecked every generated file will be
        differentiated with date at time of export.""")
    export_model_name = fields.Selection(
        selection='_list_all_models',
        string='Model',
        required=True,
        default='product.template')
    custom_export_format_id = fields.Many2one(
        string="Export format",
        comodel_name="ir.exports",
        ondelete="restrict",
        required=True,
        help="Select a custom export format, or create one first in the default Export feature wizard for the model data.",
    )
    custom_export_format_header = fields.Char(
        string="Header field names",
        help="Modify the header columns if needed.", required=True)
    export_domain = fields.Text(default='[]', required=True)
    active = fields.Boolean(default=True)
    ir_cron_id = fields.Many2one(
        string="Cron Job",
        comodel_name="ir.cron",
        ondelete="set null",
        help="Cron Job specified to run the export.",
    )
    cron_interval_number = fields.Integer(related='ir_cron_id.interval_number', string='Cron Interval Number', readonly=False)
    cron_interval_type = fields.Selection(related='ir_cron_id.interval_type', string='Cron Interval Type', readonly=False)
    cron_nextcall = fields.Datetime(related='ir_cron_id.nextcall', readonly=False)
    interval_number = fields.Integer(default=1, help="Repeat every x.", required=True)
    interval_type = fields.Selection([('minutes', 'Minutes'),
                                      ('hours', 'Hours'),
                                      ('days', 'Days'),
                                      ('weeks', 'Weeks'),
                                      ('months', 'Months')], string='Interval Unit', default='months', required=True)
    nextcall = fields.Datetime(string='Next Export At', required=True, default=fields.Datetime.now, help="Next planned execution date for this export.")
    sftp_server_id = fields.Many2one(
        string="SFTP Server",
        comodel_name="sftp.server",
        ondelete="restrict",
        required=True,
        help="SFTP server to send the exports to.",
    )

    def _list_all_models(self):
        self._cr.execute("SELECT model, name FROM ir_model ORDER BY name")
        return self._cr.fetchall()

    @api.model_create_multi
    def create(self, vals):
        custom_exports = super(CustomExporter, self).create(vals)
        custom_exports._validate_cron_job()
        return custom_exports

    def write(self, vals):
        res = super(CustomExporter, self).write(vals)
        self._validate_cron_job()
        return res

    def unlink(self):
        for rec in self:
            custom_export_files = self.env['custom.export.file'].search([('custom_exporter_id', '=', rec.id)])
            if custom_export_files:
                raise ValidationError(_('This exporter already produced files, so it can not be deleted - please archive it or instead delete all the exported files first if you want to delete it.'))
            else:
                cron_job = rec.ir_cron_id
                rec.ir_cron_id = None
                rec.flush()
                if cron_job:
                    cron_job.unlink()
        return super(CustomExporter, self).unlink()

    def _validate_cron_job(self):
        for custom_exporter in self:
            if not custom_exporter.ir_cron_id:
                # create a cron job
                vals = {
                    'name': 'Scheduler for custom export: %s' % custom_exporter.name,
                    'model_id': self.env['ir.model'].search([('model', '=', self._name)], limit=1).id,
                    'interval_number': custom_exporter.interval_number,
                    'interval_type': custom_exporter.interval_type,
                    'nextcall': custom_exporter.nextcall,
                    'code': 'model._cron_run_custom_export({custom_exporter_id})'.format(custom_exporter_id=custom_exporter.id),
                    'numbercall': -1,
                    'user_id': self.env.user.id
                }
                cron_job = self.env['ir.cron'].create(vals)
                custom_exporter.ir_cron_id = cron_job.id
            elif not custom_exporter.active:
                custom_exporter.ir_cron_id.active = False
            elif custom_exporter.active and not custom_exporter.ir_cron_id.active:
                custom_exporter.ir_cron_id.active = True

    @api.onchange('export_model_name')
    def update_export_model_name(self):
        self.custom_export_format_id = None
        self.custom_export_format_header = None
        if self.export_model_name:
            self.export_filename_prefix = self.export_model_name
        else:
            self.export_filename_prefix = None

    @api.onchange('custom_export_format_id')
    def update_custom_header(self):
        if self.custom_export_format_id:
            model_name = self.export_model_name
            context = self._context or {}
            export = Export()
            fields_name = export.namelist(model_name, self.custom_export_format_id.id)
            model = self.env[model_name].with_context(import_compat=False, **context)
            if not model._is_an_ordinary_table():
                fields_name = [field for field in fields_name if field["name"] != "id"]
            self.custom_export_format_header = [val["label"].strip() for val in fields_name] or ''

    @api.onchange('custom_export_format_header')
    def onchange_custom_header(self):
        if self.custom_export_format_header:
            try:
                ast.literal_eval(self.custom_export_format_header)
            except Exception as e:
                raise ValidationError('Custom export headers not defined correctly: %s!' % str(e))

    @profile
    def run_now(self):
        self._cron_run_custom_export()

    @profile
    def _cron_run_custom_export(self, custom_exporter_id=None):
        if custom_exporter_id:
            custom_exporter = self.browse(custom_exporter_id)
        elif self:
            custom_exporter = self
        if not custom_exporter:
            raise ValidationError('Custom Exporter Not Specified!')




        new_custom_export_file = custom_exporter.create_custom_export_file()
        domain = safe_eval(custom_exporter.export_domain)
        try:
            recordset = self.env[custom_exporter.export_model_name].search(domain)
            records_exported = len(recordset) or 0
        except Exception as e:
            recordset = False
            records_exported = 0
            msg = str(e)
            follower_ids = new_custom_export_file.message_follower_ids.mapped('partner_id').ids or []
            new_custom_export_file.message_post(body=_('Custom Exporter Error:\n\n %s.') % (msg,), message_type='email', partner_ids=follower_ids)
            _logger.warning(msg)
        file_obj = custom_exporter.generate_custom_export(new_custom_export_file, recordset)
        new_custom_export_file.attach_and_export_file(file_obj, records_exported)

    def get_custom_format_namelist(self, model, export_id):
        def fields_info(self_obj, model, export_fields):
            info = {}
            Model = self_obj.env[model]
            fields = Model.fields_get()
            if ".id" in export_fields:
                fields['.id'] = fields.get('id', {'string': 'ID'})

            for (base, length), subfields in itertools.groupby(
                    sorted(export_fields),
                    lambda field: (field.split('/', 1)[0], len(field.split('/', 1)))):
                subfields = list(subfields)
                if length == 2:
                    # subfields is a seq of $base/*rest, and not loaded yet
                    info.update(graft_subfields(
                        self_obj,
                        fields[base]['relation'], base, fields[base]['string'],
                        subfields
                    ))
                elif base in fields:
                    info[base] = fields[base]['string']

            return info

        def graft_subfields(self_obj, model, prefix, prefix_string, fields):
            export_fields = [field.split('/', 1)[1] for field in fields]
            return (
                (prefix + '/' + k, prefix_string + '/' + v)
                for k, v in fields_info(self_obj, model, export_fields).items())
        export = self.env['ir.exports'].browse([export_id]).read()[0]
        export_fields_list = self.env['ir.exports.line'].browse(export['export_fields']).read()

        fields_data = fields_info(
            self,
            model, [f['name'] for f in export_fields_list])

        return [
            {'name': field['name'], 'label': fields_data[field['name']]}
            for field in export_fields_list
        ]

    @profile
    def generate_custom_export(self, new_custom_export_file, recordset):
        export_format = self.export_format
        model_name = self.export_model_name
        try:
            fields_name = self.get_custom_format_namelist(model_name, self.custom_export_format_id.id)
            ids = recordset.ids
        except Exception as e:
            msg = 'Failed to get export fieldlist: %s' % str(e)
            follower_ids = new_custom_export_file.message_follower_ids.mapped('partner_id').ids or []
            new_custom_export_file.message_post(body=_('Custom Exporter Error:\n\n %s.') % (msg,), message_type='email', partner_ids=follower_ids)
            _logger.warning(msg)
            export = Export()
            fields_name = export.namelist(model_name, self.custom_export_format_id.id)
            ids = []
        import_compat = False
        context = self._context or {}

        model = self.env[model_name].with_context(import_compat=import_compat, **context)
        records = model.browse(ids) or model.search(self.export_domain or [], offset=0, limit=False, order=False)

        field_names = [f["name"] for f in fields_name]
        import_data = records.export_data(field_names).get("datas", [])

        if self.custom_export_format_header:
            try:
                columns_headers = ast.literal_eval(self.custom_export_format_header)
            except Exception as e:
                msg = 'Custom export headers not defined correctly: %s!' % str(e)
                follower_ids = new_custom_export_file.message_follower_ids.mapped('partner_id').ids or []
                new_custom_export_file.message_post(body=_('Custom Exporter Error:\n\n %s.') % (msg,), message_type='email', partner_ids=follower_ids)
                raise ValidationError(msg)
        else:
            if import_compat:
                columns_headers = field_names
            else:
                columns_headers = [val["label"].strip() for val in fields_name]

        if export_format == "xlsx":
            xls = ExcelExport()
            fileobj_value = xls.from_data(columns_headers, import_data)
        else:
            csv = CSVExport()
            fileobj_value = csv.from_data(columns_headers, import_data)

        if fileobj_value:
            return base64.encodestring(fileobj_value)
        else:
            return False

    @profile
    def create_custom_export_file(self):
        self.ensure_one()
        if self.fixed_filename:
            active_exports = self.env['custom.export.file'].search([
                ('custom_exporter_id' , '=', self.id),
                ('state', '=', 'draft')])
            if len(active_exports):
                raise ValidationError("""
                    There is already an export writing file %s running (ID %s)
                    wait until it's done to write file or set the
                    exporter without a fixed filename""" % (
                        self.filename, self.id))
        name = '%s_%s.%s' % (self.export_filename_prefix, str(int(time.time() * 1000)), self.export_format)
        if self.fixed_filename:
            filename = '%s.%s' % (self.export_filename_prefix, self.export_format)
        else:
            filename = name
        vals = {
            'name': name,
            'filename': filename,
            'custom_exporter_id': self.id
        }
        custom_export_file = self.env['custom.export.file'].create(vals)
        if self.message_follower_ids:
            following_partners = self.message_follower_ids.mapped('partner_id')
            subtype_ids = []
            subtype = self.env.ref("mail.mt_note")
            if subtype:
                subtype_ids = [subtype.id]
            custom_export_file.message_subscribe(partner_ids=following_partners.ids, subtype_ids=subtype_ids)
        return custom_export_file


class CustomExportFile(models.Model):
    _name = "custom.export.file"
    _description = 'Custom Export File'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date DESC'

    name = fields.Char(required=True, string='Name')
    filename = fields.Char(required=True, string='FileName')
    custom_exporter_id = fields.Many2one(
        string="Custom Exporter",
        comodel_name="custom.exporter",
        ondelete="restrict",
        required=True,
        help="Custom Exporter linked to this export.",
    )
    state = fields.Selection(
        string="State",
        selection=EXPORT_STATES,
        default='draft',
        required=True,
        track_visibility='onchange',
    )
    records_exported = fields.Integer(string="Records exported")

    @api.constrains('state', 'name', 'filename')
    def _check_unique_running(self):

       active_exports = self.search([
               ('filename' , '=', self.filename), ('state', '=', 'draft')])
       if len(active_exports) > 1:
           raise ValidationError("""
                There is already an export writing file %s
                running (%s), wait until it's done to write file or set the
                exporter without a fixed filename""" % (self.filename, self.id))

    def attach_and_export_file(self, file_obj, records_exported):
        for custom_export_file in self:
            custom_export_file.records_exported = records_exported
            if file_obj:
                custom_export_file.export_via_sftp(file_obj)

    def export_via_sftp(self, file_obj):
        for custom_export_file in self:
            if not file_obj:
                custom_export_file.state = 'no_data'
            else:
                custom_export_file.create_attachment(file_obj)
            if self._context.get('skip_sftp_transfer_when_testing'):
                custom_export_file.state = 'sent'
                _logger.info('Testing: {src_file} file successfully exported.'.format(src_file=custom_export_file.name))
                continue
            try:
                key = None
                sftp_server = custom_export_file.custom_exporter_id.sftp_server_id
                if sftp_server.protocol == 'ftp':
                    with ftplib.FTP() as ftp:
                        ftp.connect(host=sftp_server.host_address, port=sftp_server.port)
                        ftp.login(sftp_server.username, sftp_server.password)
                        ftp.cwd('/')
                        ftp.cwd(sftp_server.export_path)
                        _logger.info('FTP Exporting: {src_path}/{src_file}'.format(src_path=sftp_server.export_path,
                                                                                   src_file=custom_export_file.name))
                        filelike_obj = io.BytesIO(base64.decodebytes(file_obj))
                        ftp.storbinary('STOR %s' % custom_export_file.name, filelike_obj)
                        _logger.info('FTP Exported File: {src_path}/{src_file}'.format(src_path=sftp_server.export_path,
                                                                                       src_file=custom_export_file.name))
                        custom_export_file.state = 'sent'
                else:
                    if sftp_server.auth_type and sftp_server.auth_type == 'keyfile' and sftp_server.keyfile_type:
                        password = sftp_server.password
                        keyfile_data = base64.decodebytes(sftp_server.keyfile)
                        keyfile_obj = io.TextIOWrapper(io.BytesIO(keyfile_data), encoding='utf-8')
                        if sftp_server.keyfile_type == 'DSA':
                            if password:
                                key = paramiko.ECDSAKey.from_private_key(keyfile_obj, password)
                            else:
                                key = paramiko.ECDSAKey.from_private_key(keyfile_obj)
                        elif sftp_server.keyfile_type == 'ECDSA':
                            if password:
                                key = paramiko.DSSKey.from_private_key(keyfile_obj, password)
                            else:
                                key = paramiko.DSSKey.from_private_key(keyfile_obj)
                        elif sftp_server.keyfile_type == 'Ed25519':
                            if password:
                                key = paramiko.Ed25519Key.from_private_key(keyfile_obj, password)
                            else:
                                key = paramiko.Ed25519Key.from_private_key(keyfile_obj)
                        else:
                            # RSA key is the most common
                            if password:
                                key = paramiko.RSAKey.from_private_key(keyfile_obj, password)
                            else:
                                key = paramiko.RSAKey.from_private_key(keyfile_obj)
                    with paramiko.Transport((sftp_server.host_address, sftp_server.port)) as sftp_transport:
                        sftp_transport.connect(
                            hostkey=None,
                            username=sftp_server.username,
                            password=sftp_server.password,
                            pkey=key,
                        )
                        with paramiko.SFTPClient.from_transport(sftp_transport) as sftp:
                            sftp.chdir('/')
                            sftp.chdir(sftp_server.export_path)
                            _logger.info('SFTP Exporting: {src_path}/{src_file}'.format(src_path=sftp_server.export_path,
                                                                                        src_file=custom_export_file.name))
                            filelike_obj = io.BytesIO(base64.decodebytes(file_obj))
                            sftp.putfo(filelike_obj, custom_export_file.name)
                            _logger.info('SFTP Exported File: {src_path}/{src_file}'.format(src_path=sftp_server.export_path,
                                                                                            src_file=custom_export_file.name))
                            custom_export_file.state = 'sent'
            except Exception as e:
                msg = str(e)
                follower_ids = custom_export_file.message_follower_ids.mapped('partner_id').ids or []
                custom_export_file.message_post(body=_('Custom Exporter FTP/SFTP Error:\n\n %s.') % (msg,), message_type='email', partner_ids=follower_ids)
                _logger.warning(msg)
                custom_export_file.state = 'failed'

    def create_attachment(self, file_obj):
        attachment_obj = self.env['ir.attachment']
        for custom_export_file in self:
            vals = {
                'name': custom_export_file.name,
                'datas': file_obj,
                'type': 'binary',
                'res_model': 'custom.export.file',
                'res_id': custom_export_file.id,
            }
            attachment_obj.create(vals)
