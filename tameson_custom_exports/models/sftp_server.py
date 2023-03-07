import base64
import ftplib
import io
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

try:
    import paramiko
except Exception as e:
    raise ImportError(
        'Dependency failure: "sftp" requires python library "paramiko": %s.' % str(e)
    )


_logger = logging.getLogger(__name__)

AUTH_TYPES = [("password", "Password-based"), ("keyfile", "Key file")]
KEY_TYPES = [
    ("RSA", "RSA"),
    ("DSA", "DSA"),
    ("ECDSA", "ECDSA"),
    ("Ed25519", "Ed25519"),
]


class SFTPServer(models.Model):
    _name = "sftp.server"
    _description = "SFTP Server"

    name = fields.Char("Name", required=True)
    active = fields.Boolean("Active", default=True)
    host_address = fields.Char("Host address", required=True)
    port = fields.Integer("Port", default=22, required=True)
    export_path = fields.Char(string="Remote path to export files to", required=True)
    username = fields.Char("Username")
    password = fields.Char("Password")
    auth_type = fields.Selection(
        AUTH_TYPES, string="Authentification Type", required=True
    )
    keyfile_type = fields.Selection(KEY_TYPES, string="Key File Type")
    keyfile = fields.Binary(string="Key File")
    keyfilename = fields.Char(string="Key Filename")
    protocol = fields.Selection(
        string="Type",
        selection=[
            ("ftp", "FTP "),
            ("sftp", "SFTP"),
        ],
        default="sftp",
        required=True,
    )

    def check_connection(self):
        for sftp_server in self:
            try:
                key = None
                if sftp_server.protocol == "ftp":
                    with ftplib.FTP() as ftp:
                        ftp.connect(
                            host=sftp_server.host_address, port=sftp_server.port
                        )
                        ftp.login(sftp_server.username, sftp_server.password)
                        ftp.voidcmd("NOOP")
                        _logger.info(
                            "FTP working: {server}".format(server=sftp_server.name)
                        )
                else:
                    if (
                        sftp_server.auth_type
                        and sftp_server.auth_type == "keyfile"
                        and sftp_server.keyfile_type
                    ):
                        password = sftp_server.password
                        keyfile_data = base64.decodebytes(sftp_server.keyfile)
                        keyfile_obj = io.TextIOWrapper(
                            io.BytesIO(keyfile_data), encoding="utf-8"
                        )
                        if sftp_server.keyfile_type == "DSA":
                            if password:
                                key = paramiko.ECDSAKey.from_private_key(
                                    keyfile_obj, password
                                )
                            else:
                                key = paramiko.ECDSAKey.from_private_key(keyfile_obj)
                        elif sftp_server.keyfile_type == "ECDSA":
                            if password:
                                key = paramiko.DSSKey.from_private_key(
                                    keyfile_obj, password
                                )
                            else:
                                key = paramiko.DSSKey.from_private_key(keyfile_obj)
                        elif sftp_server.keyfile_type == "Ed25519":
                            if password:
                                key = paramiko.Ed25519Key.from_private_key(
                                    keyfile_obj, password
                                )
                            else:
                                key = paramiko.Ed25519Key.from_private_key(keyfile_obj)
                        else:
                            # RSA key is the most common
                            if password:
                                key = paramiko.RSAKey.from_private_key(
                                    keyfile_obj, password
                                )
                            else:
                                key = paramiko.RSAKey.from_private_key(keyfile_obj)
                    with paramiko.Transport(
                        (sftp_server.host_address, sftp_server.port)
                    ) as sftp_transport:
                        sftp_transport.connect(
                            hostkey=None,
                            username=sftp_server.username,
                            password=sftp_server.password,
                            pkey=key,
                        )
                        with paramiko.SFTPClient.from_transport(sftp_transport) as sftp:
                            sftp.chdir("/")
                            sftp.chdir(sftp_server.export_path)
                            _logger.info(
                                "SFTP: Current directory: {curr_dir}".format(
                                    curr_dir=sftp.listdir()
                                )
                            )
                title = _("Connection Test Succeeded!")
                message = _("Everything seems properly set up!")
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": title,
                        "message": message,
                        "sticky": False,
                    },
                }
            except Exception as e:
                msg = str(e)
                raise UserError("FTP Connection Error: {message}".format(message=msg))
