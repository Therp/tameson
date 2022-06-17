# Copyright 2015-2021 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
import base64
import mimetypes

from lxml import etree

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError
from pydifact.segmentcollection import Interchange
from datetime import datetime
logger = logging.getLogger(__name__)

def get_product_ref(line, code='BP'):
    for segment in line.get_segments('PIA'):
        if segment.elements[1][1] == code:
            return segment.elements[1][0]

def get_qty(line, code='21'):
    for segment in line.get_segments('QTY'):
        if segment.elements[0][0] == code:
            return segment.elements[0][1]

def get_total(line, code='203'):
    for segment in line.get_segments('MOA'):
        if segment.elements[0][0] == code:
            return segment.elements[0][1]

def get_rff(line, code='ON'):
    for segment in line.get_segments('RFF'):
        if segment.elements[0][0] == code:
            return segment.elements[0][1]

def get_tax(line, code='7'):
    for segment in line.get_segments('TAX'):
        if segment.elements[0] == code:
            return segment.elements[-1]

def get_desc(line, code='F'):
    for segment in line.get_segments('IMD'):
        return segment.elements[2][3]

def get_date(interchange, code='137'):
    for segment in interchange.get_segments('DTM'):
        if segment.elements[0][0] == code:
            return segment.elements[0][1]

def get_ref(interchange, code='380'):
    for segment in interchange.get_segments('BGM'):
        if segment.elements[0] == code:
            return segment.elements[1]

def get_ref(interchange, code='77'):
    for segment in interchange.get_segments('MOA'):
        if segment.elements[0] == code:
            return segment.elements[1]



class AccountInvoiceImport(models.TransientModel):
    _inherit = "account.invoice.import"

    @api.model
    def parse_invoice(self, invoice_file_b64, invoice_filename):
        assert invoice_file_b64, "No invoice file"
        assert isinstance(invoice_file_b64, bytes)
        logger.info("Starting to import invoice %s", invoice_filename)
        file_data = base64.b64decode(invoice_file_b64)
        filetype = mimetypes.guess_type(invoice_filename)
        logger.debug("Invoice mimetype: %s", filetype)

        if filetype and filetype[0] in ["application/xml", "text/xml"]:
            try:
                xml_root = etree.fromstring(file_data)
            except Exception as e:
                raise UserError(_("This XML file is not XML-compliant. Error: %s") % e)
            pretty_xml_bytes = etree.tostring(
                xml_root, pretty_print=True, encoding="UTF-8", xml_declaration=True
            )
            logger.debug("Starting to import the following XML file:")
            logger.debug(pretty_xml_bytes.decode("utf-8"))
            parsed_inv = self.parse_xml_invoice(xml_root)
            if parsed_inv is False:
                raise UserError(
                    _(
                        "This type of XML invoice is not supported. "
                        "Did you install the module to support this type "
                        "of file?"
                    )
                )
        elif 'edi' in invoice_filename:
           parsed_inv = self.parse_edi_data(file_data)
        else:
            parsed_inv = self.parse_pdf_invoice(file_data)
        if "attachments" not in parsed_inv:
            parsed_inv["attachments"] = {}
        parsed_inv["attachments"][invoice_filename] = invoice_file_b64
        # pre_process_parsed_inv() will be called again a second time,
        # but it's OK
        pp_parsed_inv = self.pre_process_parsed_inv(parsed_inv)
        return pp_parsed_inv


    def parse_edi_data(self, file_data):
        parsed_inv = {
            'lines': []
        }
        interchange = Interchange.from_str(file_data.decode('latin-1'))
        
        for line in interchange.split_by('LIN'):
            sku = get_product_ref(line,)
            if sku:
                product = {'code': sku}
            else:
                product = {'id': 93646}
            total = float(get_total(line))
            qty = float(get_qty(line))
            supcode = get_product_ref(line, 'SA')
            description = get_desc(line)
            ref = get_rff(line),
            name = "%s, %s, %s" % (ref, description, supcode)
            parsed_inv['lines'].append({
                'product': product,
                'qty': qty,
                'tax': get_tax(line),
                'price_unit': total/qty,
                'name': name,
            })
        parsed_inv['date'] = datetime.strptime(get_date(interchange), '%Y%m%d')
        parsed_inv['invoice_number'] = get_ref(interchange)
        for segments in interchange.split_by('UNS'):
            amount = float(get_total(segments, '77'))
            parsed_inv['amount_total'] = amount
            parsed_inv['amount_untaxed'] = amount
            break
        return self.edi_data_to_parsed_inv(parsed_inv)

    def edi_data_to_parsed_inv(self, data):
        parsed_inv = {
            "partner": {
                'id': 12
            },
            "currency": {
                "id": 1,
            },
            "amount_total": data.get("amount"),
            "date": data.get("date"),
            "date_due": data.get("date_due"),
            "date_start": data.get("date_start"),
            "date_end": data.get("date_end"),
            'invoice_number': data['invoice_number'],
            'lines': data['lines'],
            "type": "in_invoice",
        }
        for field in ["invoice_number", "description"]:
            if isinstance(data.get(field), list):
                parsed_inv[field] = " ".join(data[field])
            else:
                parsed_inv[field] = data.get(field)
        if "amount_total" in data:
            parsed_inv["amount_total"] = data["amount_total"]
        if "amount_untaxed" in data:
            parsed_inv["amount_untaxed"] = data["amount_untaxed"]
        if "amount_tax" in data:
            parsed_inv["amount_tax"] = data["amount_tax"]
        if "company_vat" in data:
            parsed_inv["company"] = {"vat": data["company_vat"]}
        for key, value in parsed_inv.items():
            if key.startswith("date") and value:
                parsed_inv[key] = fields.Date.to_string(value)
        return parsed_inv