# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from odoo.exceptions import UserError
from odoo.tools import pdf

from .ups_request_adapted import UPSRequest, Package


class ProviderUPS(models.Model):
    _inherit = 'delivery.carrier'

    ups_default_package_weight = fields.Float(string='Default package weight',
                                              help='If any of products in package has undefined weight, this value will be used',
                                              default=1.0)
    ups_send_notification_to_customer = fields.Boolean(string='UPS sends email notifications to the customer', default=False)
    ups_send_notification_email = fields.Char(string='UPS notification additional email')
    ups_send_notification_undelivered_email = fields.Char(string='UPS email notification to this email when customer email not delivered')

    def ups_rate_shipment(self, order):
        # methods are overriden and the edits regarding the original are marked with comments

        return {'success': True,
                'price': 0,  # Tameson edit - always show 0
                'error_message': False,
                'warning_message': False}

        superself = self.sudo()
        srm = UPSRequest(self.log_xml, superself.ups_username, superself.ups_passwd, superself.ups_shipper_number, superself.ups_access_number, self.prod_environment)
        ResCurrency = self.env['res.currency']
        max_weight = self.ups_default_packaging_id.max_weight
        packages = []
        total_qty = 0
        total_weight = 0
        for line in order.order_line.filtered(lambda line: not line.is_delivery and not line.display_type):
            total_qty += line.product_uom_qty

            # Tameson START
            if line.product_id.weight:
                total_weight += line.product_id.weight * line.product_qty
            else:
                total_weight = self.ups_default_package_weight
                break
            # Tameson END

        if max_weight and total_weight > max_weight:
            total_package = int(total_weight / max_weight)
            last_package_weight = total_weight % max_weight

            for seq in range(total_package):
                packages.append(Package(self, max_weight))
            if last_package_weight:
                packages.append(Package(self, last_package_weight))
        else:
            packages.append(Package(self, total_weight))

        shipment_info = {
            'total_qty': total_qty  # required when service type = 'UPS Worldwide Express Freight'
        }

        if self.ups_cod:
            cod_info = {
                'currency': order.partner_id.country_id.currency_id.name,
                'monetary_value': order.amount_total,
                'funds_code': self.ups_cod_funds_code,
            }
        else:
            cod_info = None

        check_value = srm.check_required_value(order.company_id.partner_id, 
                                               order.warehouse_id.partner_id, 
                                               order.partner_shipping_id, 
                                               order=order,
                                               default_package_weight=superself.ups_default_package_weight)  # Tameson edit: add default weight
        if check_value:
            return {'success': False,
                    'price': 0.0,
                    'error_message': check_value,
                    'warning_message': False}

        ups_service_type = order.ups_service_type or self.ups_default_service_type
        result = srm.get_shipping_price(
            shipment_info=shipment_info, packages=packages, shipper=order.company_id.partner_id, ship_from=order.warehouse_id.partner_id,
            ship_to=order.partner_shipping_id, packaging_type=self.ups_default_packaging_id.shipper_package_code, service_type=ups_service_type,
            saturday_delivery=self.ups_saturday_delivery, cod_info=cod_info)

        if result.get('error_message'):
            return {'success': False,
                    'price': 0.0,
                    'error_message': _('Error:\n%s') % result['error_message'],
                    'warning_message': False}

        if order.currency_id.name == result['currency_code']:
            price = float(result['price'])
        else:
            quote_currency = ResCurrency.search([('name', '=', result['currency_code'])], limit=1)
            price = quote_currency._convert(
                float(result['price']), order.currency_id, order.company_id, order.date_order or fields.Date.today())

        if self.ups_bill_my_account and order.ups_carrier_account:
            # Don't show delivery amount, if ups bill my account option is true
            price = 0.0

        return {'success': True,
                'price': price,
                'error_message': False,
                'warning_message': False}

    def ups_send_shipping(self, pickings):
        res = []
        superself = self.sudo()
        srm = UPSRequest(self.log_xml, superself.ups_username, superself.ups_passwd, superself.ups_shipper_number, superself.ups_access_number, self.prod_environment)
        ResCurrency = self.env['res.currency']
        for picking in pickings:
            packages = []
            package_names = []
            if picking.package_ids:
                # Create all packages
                for package in picking.package_ids:  # Tameson edit: add default package weight
                    packages.append(Package(self, package.shipping_weight or superself.ups_default_package_weight, quant_pack=package.packaging_id, name=package.name))
                    package_names.append(package.name)
            # Create one package with the rest (the content that is not in a package)
            if picking.weight_bulk or (not packages and superself.ups_default_package_weight):  # Tameson edit: add default package weight
                packages.append(Package(self, picking.weight_bulk or superself.ups_default_package_weight))

            invoice_line_total = 0
            for move in picking.move_lines:
                invoice_line_total += picking.company_id.currency_id.round(move.product_id.lst_price * move.product_qty)

            shipment_info = {
                'description': picking.origin,
                'total_qty': sum(sml.qty_done for sml in picking.move_line_ids),
                'ilt_monetary_value': '%d' % invoice_line_total,
                'itl_currency_code': self.env.company.currency_id.name,
                'phone': picking.partner_id.mobile or picking.partner_id.phone or picking.sale_id.partner_id.mobile or picking.sale_id.partner_id.phone,
            }
            if picking.sale_id and picking.sale_id.carrier_id != picking.carrier_id:
                ups_service_type = picking.carrier_id.ups_default_service_type or picking.ups_service_type or self.ups_default_service_type
            else:
                ups_service_type = picking.ups_service_type or self.ups_default_service_type
            ups_carrier_account = picking.ups_carrier_account

            if picking.carrier_id.ups_cod:
                cod_info = {
                    'currency': picking.partner_id.country_id.currency_id.name,
                    'monetary_value': picking.sale_id.amount_total,
                    'funds_code': self.ups_cod_funds_code,
                }
            else:
                cod_info = None

            check_value = srm.check_required_value(picking.company_id.partner_id,
                                                   picking.picking_type_id.warehouse_id.partner_id,
                                                   picking.partner_id,
                                                   picking=picking,
                                                   default_package_weight=superself.ups_default_package_weight)  # Tameson edit: add default weight
            if check_value:
                raise UserError(check_value)

            package_type = picking.package_ids and picking.package_ids[0].packaging_id.shipper_package_code or self.ups_default_packaging_id.shipper_package_code

            # Tameson START
            partner_email = picking.partner_id.email
            if not partner_email and picking.partner_id.parent_id:
                partner_email = picking.partner_id.parent_id.email

            access_point_id = picking.presta_ups_access_point_id
            access_point_country = picking.presta_ups_access_point_country
            access_point_phone = picking.partner_id.mobile or picking.partner_id.phone

            srm.send_shipping(
                shipment_info=shipment_info,
                packages=packages,
                shipper=picking.company_id.partner_id,
                ship_from=picking.picking_type_id.warehouse_id.partner_id,
                ship_to=picking.partner_id,
                packaging_type=package_type,
                service_type=ups_service_type,
                saturday_delivery=picking.carrier_id.ups_saturday_delivery,
                duty_payment=picking.carrier_id.ups_duty_payment,
                cod_info=cod_info,
                access_point_id=access_point_id,
                access_point_country=access_point_country,
                access_point_phone=access_point_phone,
                label_file_type=self.ups_label_file_type,
                send_notification=superself.ups_send_notification_to_customer,
                send_notification_emails=[partner_email, superself.ups_send_notification_email],
                uap_shipper_email=superself.ups_send_notification_email,
                send_notification_undelivered_email=superself.ups_send_notification_undelivered_email,
                ups_carrier_account=ups_carrier_account)
            # Tameson END
            result = srm.process_shipment()
            if result.get('error_message'):
                # Tameson edit
                error = 'Orders: %s\n\n%s' % (
                    ', '.join('%s [picking %s]' % (sp.origin, sp.name) for sp in pickings),
                    result['error_message']
                )
                raise UserError(error)

            order = picking.sale_id
            company = order.company_id or picking.company_id or self.env.company
            currency_order = picking.sale_id.currency_id
            if not currency_order:
                currency_order = picking.company_id.currency_id

            if currency_order.name == result['currency_code']:
                price = float(result['price'])
            else:
                quote_currency = ResCurrency.search([('name', '=', result['currency_code'])], limit=1)
                price = quote_currency._convert(
                    float(result['price']), currency_order, company, order.date_order or fields.Date.today())

            package_labels = []
            for track_number, label_binary_data in result.get('label_binary_data').items():
                package_labels = package_labels + [(track_number, label_binary_data)]

            carrier_tracking_ref = "+".join([pl[0] for pl in package_labels])
            logmessage = _("Shipment created into UPS<br/>"
                           "<b>Tracking Numbers:</b> %s<br/>"
                           "<b>Packages:</b> %s") % (carrier_tracking_ref, ','.join(package_names))
            if self.ups_label_file_type != 'GIF':
                attachments = [('LabelUPS-%s.%s' % (pl[0], self.ups_label_file_type), pl[1]) for pl in package_labels]
            if self.ups_label_file_type == 'GIF':
                attachments = [('LabelUPS.pdf', pdf.merge_pdf([pl[1] for pl in package_labels]))]
            picking.message_post(body=logmessage, attachments=attachments)
            shipping_data = {
                'exact_price': price,
                'tracking_number': carrier_tracking_ref}
            res = res + [shipping_data]
            if self.return_label_on_delivery:
                self.ups_get_return_label(picking)
        return res

    def ups_get_return_label(self, picking, tracking_number=None, origin_date=None):
        res = []
        superself = self.sudo()
        srm = UPSRequest(self.log_xml, superself.ups_username, superself.ups_passwd, superself.ups_shipper_number, superself.ups_access_number, self.prod_environment)
        ResCurrency = self.env['res.currency']
        packages = []
        package_names = []
        if picking.is_return_picking:
            weight = sum([m.product_id.weight * m.product_qty for m in picking.move_lines])
            packages.append(Package(self, weight))
        else:
            if picking.package_ids:
                # Create all packages
                for package in picking.package_ids:
                    packages.append(Package(self, package.shipping_weight, quant_pack=package.packaging_id, name=package.name))
                    package_names.append(package.name)
            # Create one package with the rest (the content that is not in a package)
            if picking.weight_bulk:
                packages.append(Package(self, picking.weight_bulk))

        invoice_line_total = 0
        for move in picking.move_lines:
            invoice_line_total += picking.company_id.currency_id.round(move.product_id.lst_price * move.product_qty)

        shipment_info = {
            'description': picking.origin,
            'total_qty': sum(sml.qty_done for sml in picking.move_line_ids),
            'ilt_monetary_value': '%d' % invoice_line_total,
            'itl_currency_code': self.env.company.currency_id.name,
            'phone': picking.partner_id.mobile or picking.partner_id.phone or picking.sale_id.partner_id.mobile or picking.sale_id.partner_id.phone,
        }
        if picking.sale_id and picking.sale_id.carrier_id != picking.carrier_id:
            ups_service_type = picking.carrier_id.ups_default_service_type or picking.ups_service_type or self.ups_default_service_type
        else:
            ups_service_type = picking.ups_service_type or self.ups_default_service_type
        ups_carrier_account = picking.ups_carrier_account

        if picking.carrier_id.ups_cod:
            cod_info = {
                'currency': picking.partner_id.country_id.currency_id.name,
                'monetary_value': picking.sale_id.amount_total,
                'funds_code': self.ups_cod_funds_code,
            }
        else:
            cod_info = None

        check_value = srm.check_required_value(picking.partner_id, picking.partner_id, picking.picking_type_id.warehouse_id.partner_id)
        if check_value:
            raise UserError(check_value)

        package_type = picking.package_ids and picking.package_ids[0].packaging_id.shipper_package_code or self.ups_default_packaging_id.shipper_package_code

        srm.send_shipping(
            shipment_info=shipment_info,
            packages=packages,
            shipper=picking.partner_id,
            ship_from=picking.partner_id,
            ship_to=picking.picking_type_id.warehouse_id.partner_id,
            packaging_type=package_type,
            service_type=ups_service_type,
            saturday_delivery=picking.carrier_id.ups_saturday_delivery,
            duty_payment='RECIPIENT',
            cod_info=cod_info,
            label_file_type=self.ups_label_file_type,
            ups_carrier_account=ups_carrier_account
            )
        srm.return_label()
        result = srm.process_shipment()
        if result.get('error_message'):
            raise UserError(result['error_message'].__str__())

        order = picking.sale_id
        company = order.company_id or picking.company_id or self.env.company
        currency_order = picking.sale_id.currency_id
        if not currency_order:
            currency_order = picking.company_id.currency_id

        if currency_order.name == result['currency_code']:
            price = float(result['price'])
        else:
            quote_currency = ResCurrency.search([('name', '=', result['currency_code'])], limit=1)
            price = quote_currency._convert(
                float(result['price']), currency_order, company, order.date_order or fields.Date.today())

        package_labels = []
        for track_number, label_binary_data in result.get('label_binary_data').items():
            package_labels = package_labels + [(track_number, label_binary_data)]

        carrier_tracking_ref = "+".join([pl[0] for pl in package_labels])
        logmessage = _("Return label generated<br/>"
                       "<b>Tracking Numbers:</b> %s<br/>"
                       "<b>Packages:</b> %s") % (carrier_tracking_ref, ','.join(package_names))
        if self.ups_label_file_type != 'GIF':
            attachments = [('%s-%s-%s.%s' % (self.get_return_label_prefix(), pl[0], index, self.ups_label_file_type), pl[1]) for index, pl in enumerate(package_labels)]
        if self.ups_label_file_type == 'GIF':
            attachments = [('%s-%s-%s.%s' % (self.get_return_label_prefix(), package_labels[0][0], 1, 'pdf'), pdf.merge_pdf([pl[1] for pl in package_labels]))]
        picking.message_post(body=logmessage, attachments=attachments)
        shipping_data = {
            'exact_price': price,
            'tracking_number': carrier_tracking_ref}
        res = res + [shipping_data]
        return res

    def ups_cancel_shipment(self, picking):
        tracking_ref = picking.carrier_tracking_ref
        if not self.prod_environment:
            tracking_ref = "1ZISDE016691676846"  # used for testing purpose

        superself = self.sudo()
        srm = UPSRequest(self.log_xml, superself.ups_username, superself.ups_passwd, superself.ups_shipper_number, superself.ups_access_number, self.prod_environment)
        result = srm.cancel_shipment(tracking_ref.partition('+')[0])

        if result.get('error_message'):
            # Tameson edit
            error = 'Order: %s\n\n%s' % (
                '%s [picking %s]' % (picking.origin, picking.name),
                result['error_message']
            )
            raise UserError(error)
        else:
            picking.message_post(body=_(u'Shipment N° %s has been cancelled' % picking.carrier_tracking_ref))
            picking.write({'carrier_tracking_ref': '',
                           'carrier_price': 0.0})
