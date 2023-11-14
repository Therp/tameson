from odoo.tests.common import TransactionCase


class TestCustomExporter(TransactionCase):
    def setUp(self):
        super(TestCustomExporter, self).setUp()

        self.custom_export_format = self.env["ir.exports"].create(
            {
                "name": "Testing format",
                "resource": "product.template",
                "export_fields": [
                    (0, 0, {"name": "sequence"}),
                    (0, 0, {"name": "default_code"}),
                    (0, 0, {"name": "list_price"}),
                ],
            }
        )
        self.export_model_name = "product.template"
        self.custom_export_format_header = "['Seq', 'SKU', 'Price']"
        self.sftp_server = self.env["sftp.server"].create(
            {
                "name": "Testing SFTP server",
                "host_address": "test.example.org",
                "port": 22,
                "export_path": "/tmp",
                "auth_type": "password",
            }
        )
        self.test_custom_exporter = self.env["custom.exporter"].create(
            {
                "name": "Testing",
                "export_format": "csv",
                "export_filename_prefix": "testing_",
                "export_model_name": self.export_model_name,
                "custom_export_format_id": self.custom_export_format.id,
                "custom_export_format_header": self.custom_export_format_header,
                "interval_number": 1,
                "interval_type": "days",
                "sftp_server_id": self.sftp_server.id,
            }
        )

    def test_call_custom_exporter_testing(self):
        # run the exporter
        print(self.test_custom_exporter)
        self.env["custom.exporter"].with_context(
            skip_sftp_transfer_when_testing=True
        )._cron_run_custom_export(self.test_custom_exporter.id)

        # make sure there is 1 export file record
        export_files = self.env["custom.export.file"].search(
            [("custom_exporter_id", "=", self.test_custom_exporter.id)]
        )
        self.assertEqual(len(export_files), 1)
        # check if the state is sent (SFTP is not tested, we just mock it to be sent if everything else goes through)
        self.assertEqual(export_files.state, "sent")
