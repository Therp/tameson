# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import io
import logging
import os
import re

import PIL.PdfImagePlugin  # activate PDF support in PIL
import requests
from PIL import Image
from zeep import Client, Plugin
from zeep.exceptions import Fault
from zeep.wsdl.utils import etree_to_string

from odoo import _, _lt

_logger = logging.getLogger(__name__)
# uncomment to enable logging of SOAP requests and responses
# logging.getLogger('zeep.transports').setLevel(logging.DEBUG)


UPS_ERROR_MAP = {
    "110002": _lt("Please provide at least one item to ship."),
    "110208": _lt("Please set a valid country in the recipient address."),
    "110308": _lt("Please set a valid country in the warehouse address."),
    "110548": _lt(
        "A shipment cannot have a KGS/IN or LBS/CM as its unit of measurements. Configure it from the delivery method."
    ),
    "111057": _lt(
        "This measurement system is not valid for the selected country. Please switch from LBS/IN to KGS/CM (or vice versa). Configure it from the delivery method."
    ),
    "111091": _lt(
        "The selected service is not possible from your warehouse to the recipient address, please choose another service."
    ),
    "111100": _lt(
        "The selected service is invalid from the requested warehouse, please choose another service."
    ),
    "111107": _lt("Please provide a valid zip code in the warehouse address."),
    "111210": _lt(
        "The selected service is invalid to the recipient address, please choose another service."
    ),
    "111212": _lt(
        "Please provide a valid package type available for service and selected locations."
    ),
    "111500": _lt("The selected service is not valid with the selected packaging."),
    "112111": _lt("Please provide a valid shipper number/Carrier Account."),
    "113020": _lt("Please provide a valid zip code in the warehouse address."),
    "113021": _lt("Please provide a valid zip code in the recipient address."),
    "120031": _lt(
        "Exceeds Total Number of allowed pieces per World Wide Express Shipment."
    ),
    "120100": _lt("Please provide a valid shipper number/Carrier Account."),
    "120102": _lt("Please provide a valid street in shipper's address."),
    "120105": _lt("Please provide a valid city in the shipper's address."),
    "120106": _lt("Please provide a valid state in the shipper's address."),
    "120107": _lt("Please provide a valid zip code in the shipper's address."),
    "120108": _lt("Please provide a valid country in the shipper's address."),
    "120109": _lt("Please provide a valid shipper phone number."),
    "120113": _lt("Shipper number must contain alphanumeric characters only."),
    "120114": _lt("Shipper phone extension cannot exceed the length of 4."),
    "120115": _lt("Shipper Phone must be at least 10 alphanumeric characters."),
    "120116": _lt("Shipper phone extension must contain only numbers."),
    "120122": _lt("Please provide a valid shipper Number/Carrier Account."),
    "120124": _lt(
        "The requested service is unavailable between the selected locations."
    ),
    "120202": _lt("Please provide a valid street in the recipient address."),
    "120205": _lt("Please provide a valid city in the recipient address."),
    "120206": _lt("Please provide a valid state in the recipient address."),
    "120207": _lt("Please provide a valid zipcode in the recipient address."),
    "120208": _lt("Please provide a valid Country in recipient's address."),
    "120209": _lt("Please provide a valid phone number for the recipient."),
    "120212": _lt("Recipient PhoneExtension cannot exceed the length of 4."),
    "120213": _lt("Recipient Phone must be at least 10 alphanumeric characters."),
    "120214": _lt("Recipient PhoneExtension must contain only numbers."),
    "120302": _lt("Please provide a valid street in the warehouse address."),
    "120305": _lt("Please provide a valid City in the warehouse address."),
    "120306": _lt("Please provide a valid State in the warehouse address."),
    "120307": _lt("Please provide a valid Zip in the warehouse address."),
    "120308": _lt("Please provide a valid Country in the warehouse address."),
    "120309": _lt("Please provide a valid warehouse Phone Number"),
    "120312": _lt("Warehouse PhoneExtension cannot exceed the length of 4."),
    "120313": _lt("Warehouse Phone must be at least 10 alphanumeric characters."),
    "120314": _lt("Warehouse Phone must contain only numbers."),
    "120412": _lt("Please provide a valid shipper Number/Carrier Account."),
    "121057": _lt(
        "This measurement system is not valid for the selected country. Please switch from LBS/IN to KGS/CM (or vice versa). Configure it from delivery method"
    ),
    "121210": _lt(
        "The requested service is unavailable between the selected locations."
    ),
    "128089": _lt(
        "Access License number is Invalid. Provide a valid number (Length sholuld be 0-35 alphanumeric characters)"
    ),
    "190001": _lt(
        "Cancel shipment not available at this time , Please try again Later."
    ),
    "190100": _lt("Provided Tracking Ref. Number is invalid."),
    "190109": _lt("Provided Tracking Ref. Number is invalid."),
    "250001": _lt(
        "Access License number is invalid for this provider.Please re-license."
    ),
    "250002": _lt("Username/Password is invalid for this delivery provider."),
    "250003": _lt("Access License number is invalid for this delivery provider."),
    "250004": _lt("Username/Password is invalid for this delivery provider."),
    "250006": _lt(
        "The maximum number of user access attempts was exceeded. So please try again later"
    ),
    "250007": _lt("The UserId is currently locked out; please try again in 24 hours."),
    "250009": _lt("Provided Access License Number not found in the UPS database"),
    "250038": _lt("Please provide a valid shipper number/Carrier Account."),
    "250047": _lt("Access License number is revoked contact UPS to get access."),
    "250052": _lt("Authorization system is currently unavailable , try again later."),
    "250053": _lt("UPS Server Not Found"),
    "9120200": _lt("Please provide at least one item to ship"),
}


SHIPMENT_INDICATION_TYPES = {
    "hold-for-pickup-access-point": "01",
    "access-point-delivery": "02",
}

NOTIFICATION_CODES = {
    "qv-ship": "6",
    "alternate-delivery-location": "012",
    "uap-shipper": "013",
    "qv-exception": "7",
}

NULL_PHONE_RE = re.compile(r"^[0\s]$")  # Validation for empty phone number


class Package:
    def __init__(self, carrier, weight, quant_pack=False, name=""):
        self.weight = carrier._ups_convert_weight(
            weight, carrier.ups_package_weight_unit
        )
        self.weight_unit = carrier.ups_package_weight_unit
        self.name = name
        self.dimension_unit = carrier.ups_package_dimension_unit
        if quant_pack:
            self.dimension = {
                "length": quant_pack.length,
                "width": quant_pack.width,
                "height": quant_pack.height,
            }
        else:
            self.dimension = {
                "length": carrier.ups_default_packaging_id.length,
                "width": carrier.ups_default_packaging_id.width,
                "height": carrier.ups_default_packaging_id.height,
            }
        self.packaging_type = quant_pack and quant_pack.shipper_package_code or False


class LogPlugin(Plugin):
    """Small plugin for zeep that catches out/ingoing XML requests and logs them"""

    def __init__(self, debug_logger):
        self.debug_logger = debug_logger

    def egress(self, envelope, http_headers, operation, binding_options):
        self.debug_logger(etree_to_string(envelope).decode(), "ups_request")
        return envelope, http_headers

    def ingress(self, envelope, http_headers, operation):
        self.debug_logger(etree_to_string(envelope).decode(), "ups_response")
        return envelope, http_headers


class FixRequestNamespacePlug(Plugin):
    def __init__(self, root):
        self.root = root

    def marshalled(self, context):
        context.envelope = context.envelope.prune()


class UPSRequest(object):
    PRODUCTION_URL = "https://onlinetools.ups.com/webservices/"
    TEST_URL = "https://wwwcie.ups.com/webservices/"

    MAX_ADDRESS_LENGTH = 35
    NAME_LENGTH = 35

    LOCATOR_WSDL = "../api/Locator.wsdl"
    RATE_WSDL = "../api/RateWS.wsdl"
    SHIP_WSDL = "../api/Ship.wsdl"
    VOID_WSDL = "../api/Void.wsdl"

    @staticmethod
    def sanitize_addresses(address_lines):
        ret = []
        for line in address_lines:
            if line:
                ret.extend(
                    UPSRequest.split_by_length(line, UPSRequest.MAX_ADDRESS_LENGTH)
                )

        return ret[:3]  # spec allows max 3 address lines

    @staticmethod
    def split_by_length(s, length):
        ret = []

        def split_part(ss):
            ss = ss.strip()

            if len(ss) <= length:
                return ss, ""

            head_ss, tail_ss = ss[:length], ss[length:]

            if tail_ss and tail_ss[0] == " ":
                return head_ss, tail_ss

            splits = head_ss.split(" ")
            sinit = " ".join(splits[:-1])

            if not sinit:
                return head_ss, tail_ss

            return sinit, splits[-1] + tail_ss

        ss = s
        while ss:
            to_add, ss = split_part(ss)
            ret.append(to_add)

        return ret

    def __init__(
        self,
        debug_logger,
        username,
        password,
        shipper_number,
        access_number,
        prod_environment,
    ):
        self.debug_logger = debug_logger
        # Product and Testing url
        self.prod_environment = prod_environment
        self.endurl = "https://onlinetools.ups.com/webservices/"
        if not prod_environment:
            self.endurl = "https://wwwcie.ups.com/webservices/"

        # Basic detail require to authenticate
        self.username = username
        self.password = password
        self.shipper_number = shipper_number
        self.access_number = access_number

        self.rate_wsdl = "../api/RateWS.wsdl"
        self.ship_wsdl = "../api/Ship.wsdl"
        self.void_wsdl = "../api/Void.wsdl"
        self.ns = {"err": "http://www.ups.com/XMLSchema/XOLTWS/Error/v1.1"}

    def _add_security_header(self, client, api):
        # set the detail which require to authenticate
        user_token = {"Username": self.username, "Password": self.password}
        access_token = {"AccessLicenseNumber": self.access_number}
        security = client.get_element("ns0:UPSSecurity")(
            UsernameToken=user_token, ServiceAccessToken=access_token
        )
        client.set_default_soapheaders([security])

    def _set_service(self, client, api):
        service = client.create_service(
            next(iter(client.wsdl.bindings)), "%s%s" % (self.endurl, api)
        )
        return service

    def _set_client(self, wsdl, api, root):
        wsdl_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), wsdl)
        client = Client(
            "file:///%s" % wsdl_path.lstrip("/"),
            plugins=[FixRequestNamespacePlug(root), LogPlugin(self.debug_logger)],
        )
        self.factory_ns2 = client.type_factory("ns2")
        self.factory_ns3 = client.type_factory("ns3")
        self._add_security_header(client, api)
        return client

    def _clean_phone_number(self, phone):
        phone = re.sub("[^0-9]", "", phone)
        return "%s%s" % ("0" * (10 - len(phone)), phone)

    # TODO: add checking of access point id
    def check_required_value(
        self,
        shipper,
        ship_from,
        ship_to,
        order=False,
        picking=False,
        default_package_weight=None,
    ):
        required_field = {
            "city": "City",
            "zip": "ZIP code",
            "country_id": "Country",
            "phone": "Phone",
        }
        # Check required field for shipper
        res = [required_field[field] for field in required_field if not shipper[field]]
        if shipper.country_id.code in ("US", "CA") and not shipper.state_id.code:
            res.append("State")
        if not shipper.street and not shipper.street2:
            res.append("Street")
        if res:
            return _(
                "The address of your company is missing or wrong.\n(Missing field(s) : %s)"
            ) % ",".join(res)
        if len(self._clean_phone_number(shipper.phone)) < 8:
            return _(UPS_ERROR_MAP.get("120115"))
        # Check required field for warehouse address
        res = [
            required_field[field] for field in required_field if not ship_from[field]
        ]
        if ship_from.country_id.code in ("US", "CA") and not ship_from.state_id.code:
            res.append("State")
        if not ship_from.street and not ship_from.street2:
            res.append("Street")
        if res:
            return _(
                "The address of your warehouse is missing or wrong.\n(Missing field(s) : %s)"
            ) % ",".join(res)
        if len(self._clean_phone_number(ship_from.phone)) < 8:
            return _(UPS_ERROR_MAP.get("120313"))
        # Check required field for recipient address
        res = [
            required_field[field]
            for field in required_field
            if field != "phone" and not ship_to[field]
        ]
        if ship_to.country_id.code in ("US", "CA") and not ship_to.state_id.code:
            res.append("State")
        if not ship_to.street and not ship_to.street2:
            res.append("Street")
        # if len(ship_to.street or '') > 35 or len(ship_to.street2 or '') > 35:
        #     return _("UPS address lines can only contain a maximum of 35 characters. You can split the contacts addresses on multiple lines to try to avoid this limitation.")
        if picking and not order:
            order = picking.sale_id
        phone = ship_to.mobile or ship_to.phone
        if order and not phone:
            phone = order.partner_id.mobile or order.partner_id.phone
        if order:
            if not order.order_line:
                return _("Please provide at least one item to ship.")
            if not default_package_weight:
                for line in order.order_line.filtered(
                    lambda line: not line.product_id.weight
                    and not line.is_delivery
                    and line.product_id.type not in ["service", "digital", False]
                ):
                    return _(
                        "The estimated price cannot be computed because the weight of your product is missing."
                    )
        if picking:
            if not default_package_weight:
                for ml in picking.move_line_ids.filtered(
                    lambda ml: not ml.result_package_id and not ml.product_id.weight
                ):
                    return _(
                        "The delivery cannot be done because the weight of your product is missing."
                    )
            packages_without_weight = picking.move_line_ids.mapped(
                "result_package_id"
            ).filtered(lambda p: not p.shipping_weight)
            if packages_without_weight:
                return _("Packages %s do not have a positive shipping weight.") % (
                    ", ".join(packages_without_weight.mapped("display_name"))
                )
        if not phone:
            res.append("Phone")
        if res:
            return _(
                "The recipient address is missing or wrong.\n(Missing field(s) : %s)"
            ) % ",".join(res)
        if len(self._clean_phone_number(phone)) < 10:
            return _(UPS_ERROR_MAP.get("120213"))
        return False

    def get_error_message(self, error_code, description):
        result = {}
        result["error_message"] = "UPS ERROR %s (%s): %s" % (
            error_code,
            description,
            UPS_ERROR_MAP.get(error_code),
        )
        if not result["error_message"]:
            result["error_message"] = description
        return result

    def save_label(self, image64, label_file_type="GIF"):
        img_decoded = base64.decodebytes(image64.encode("utf-8"))
        if label_file_type == "GIF":
            # Label format is GIF, so need to rotate and convert as PDF
            image_string = io.BytesIO(img_decoded)
            im = Image.open(image_string)
            label_result = io.BytesIO()
            im.save(label_result, "pdf")
            return label_result.getvalue()
        else:
            return img_decoded

    def set_package_detail(
        self,
        client,
        packages,
        packaging_type,
        ship_from,
        ship_to,
        cod_info,
        request_type,
    ):
        Packages = []
        if request_type == "rating":
            MeasurementType = self.factory_ns2.CodeDescriptionType
        elif request_type == "shipping":
            MeasurementType = self.factory_ns2.ShipUnitOfMeasurementType
        for i, p in enumerate(packages):
            package = self.factory_ns2.PackageType()
            if hasattr(package, "Packaging"):
                package.Packaging = self.factory_ns2.PackagingType()
                package.Packaging.Code = p.packaging_type or packaging_type or ""
            elif hasattr(package, "PackagingType"):
                package.PackagingType = self.factory_ns2.CodeDescriptionType()
                package.PackagingType.Code = p.packaging_type or packaging_type or ""

            if p.dimension_unit and any(p.dimension.values()):
                package.Dimensions = self.factory_ns2.DimensionsType()
                package.Dimensions.UnitOfMeasurement = MeasurementType()
                package.Dimensions.UnitOfMeasurement.Code = p.dimension_unit or ""
                package.Dimensions.Length = p.dimension["length"] or ""
                package.Dimensions.Width = p.dimension["width"] or ""
                package.Dimensions.Height = p.dimension["height"] or ""

            if cod_info:
                package.PackageServiceOptions = (
                    self.factory_ns2.PackageServiceOptionsType()
                )
                package.PackageServiceOptions.COD = self.factory_ns2.CODType()
                package.PackageServiceOptions.COD.CODFundsCode = str(
                    cod_info["funds_code"]
                )
                package.PackageServiceOptions.COD.CODAmount = (
                    self.factory_ns2.CODAmountType()
                    if request_type == "rating"
                    else self.factory_ns2.CurrencyMonetaryType()
                )
                package.PackageServiceOptions.COD.CODAmount.MonetaryValue = cod_info[
                    "monetary_value"
                ]
                package.PackageServiceOptions.COD.CODAmount.CurrencyCode = cod_info[
                    "currency"
                ]

            package.PackageWeight = self.factory_ns2.PackageWeightType()
            package.PackageWeight.UnitOfMeasurement = MeasurementType()
            package.PackageWeight.UnitOfMeasurement.Code = p.weight_unit or ""
            package.PackageWeight.Weight = p.weight or ""

            # Package and shipment reference text is only allowed for shipments within
            # the USA and within Puerto Rico. This is a UPS limitation.
            if (
                p.name
                and ship_from.country_id.code in ("US")
                and ship_to.country_id.code in ("US")
            ):
                reference_number = self.factory_ns2.ReferenceNumberType()
                reference_number.Code = "PM"
                reference_number.Value = p.name
                reference_number.BarCodeIndicator = p.name
                package.ReferenceNumber = reference_number

            Packages.append(package)
        return Packages

    def get_shipping_price(
        self,
        shipment_info,
        packages,
        shipper,
        ship_from,
        ship_to,
        packaging_type,
        service_type,
        saturday_delivery,
        cod_info,
    ):
        client = self._set_client(self.RATE_WSDL, "Rate", "RateRequest")
        service = self._set_service(client, "Rate")
        request = self.factory_ns3.RequestType()
        request.RequestOption = "Rate"

        classification = self.factory_ns2.CodeDescriptionType()
        classification.Code = "00"  # Get rates for the shipper account
        classification.Description = "Get rates for the shipper account"

        request_type = "rating"
        shipment = self.factory_ns2.ShipmentType()

        for package in self.set_package_detail(
            client, packages, packaging_type, ship_from, ship_to, cod_info, request_type
        ):
            shipment.Package.append(package)

        shipment.Shipper = self.factory_ns2.ShipperType()
        shipment.Shipper.Name = shipper.name or ""
        shipment.Shipper.Address = self.factory_ns2.AddressType()
        shipment.Shipper.Address.AddressLine = self.sanitize_addresses(
            [shipper.street, shipper.street2]
        )
        shipment.Shipper.Address.City = shipper.city or ""
        shipment.Shipper.Address.PostalCode = shipper.zip or ""
        shipment.Shipper.Address.CountryCode = shipper.country_id.code or ""
        if shipper.country_id.code in ("US", "CA"):
            shipment.Shipper.Address.StateProvinceCode = shipper.state_id.code or ""
        shipment.Shipper.ShipperNumber = self.shipper_number or ""
        # shipment.Shipper.Phone.Number = shipper.phone or ''

        shipment.ShipFrom = self.factory_ns2.ShipFromType()
        shipment.ShipFrom.Name = ship_from.name or ""
        shipment.ShipFrom.Address = self.factory_ns2.AddressType()
        shipment.ShipFrom.Address.AddressLine = self.sanitize_addresses(
            [ship_from.street, ship_from.street2]
        )
        shipment.ShipFrom.Address.City = ship_from.city or ""
        shipment.ShipFrom.Address.PostalCode = ship_from.zip or ""
        shipment.ShipFrom.Address.CountryCode = ship_from.country_id.code or ""
        if ship_from.country_id.code in ("US", "CA"):
            shipment.ShipFrom.Address.StateProvinceCode = ship_from.state_id.code or ""
        # shipment.ShipFrom.Phone.Number = ship_from.phone or ''

        shipment.ShipTo = self.factory_ns2.ShipToType()
        shipment.ShipTo.Name = ship_to.name or ""
        shipment.ShipTo.Address = self.factory_ns2.AddressType()
        shipment.ShipTo.Address.AddressLine = self.sanitize_addresses(
            [ship_to.street, ship_to.street2]
        )
        shipment.ShipTo.Address.City = ship_to.city or ""
        shipment.ShipTo.Address.PostalCode = ship_to.zip or ""
        shipment.ShipTo.Address.CountryCode = ship_to.country_id.code or ""
        if ship_to.country_id.code in ("US", "CA"):
            shipment.ShipTo.Address.StateProvinceCode = ship_to.state_id.code or ""
        if ship_to.country_id.code in ("IE"):
            shipment.ShipTo.Address.StateProvinceCode = ship_to.state_id.code or "--"
        # shipment.ShipTo.Phone.Number = ship_to.phone or ''
        # if not ship_to.commercial_partner_id.is_company:
        #     shipment.ShipTo.Address.ResidentialAddressIndicator = None

        shipment.Service = self.factory_ns2.CodeDescriptionType()
        shipment.Service.Code = service_type or ""
        shipment.Service.Description = "Service Code"
        if service_type == "96":
            shipment.NumOfPieces = int(shipment_info.get("total_qty"))

        if saturday_delivery:
            shipment.ShipmentServiceOptions = (
                self.factory_ns2.ShipmentServiceOptionsType()
            )
            shipment.ShipmentServiceOptions.SaturdayDeliveryIndicator = (
                saturday_delivery
            )
        else:
            shipment.ShipmentServiceOptions = ""

        shipment.ShipmentRatingOptions = self.factory_ns2.ShipmentRatingOptionsType()
        shipment.ShipmentRatingOptions.NegotiatedRatesIndicator = 1

        try:
            # Get rate using for provided detail
            response = service.ProcessRate(
                Request=request,
                CustomerClassification=classification,
                Shipment=shipment,
            )

            # Check if ProcessRate is not success then return reason for that
            if response.Response.ResponseStatus.Code != "1":
                return self.get_error_message(
                    response.Response.ResponseStatus.Code,
                    response.Response.ResponseStatus.Description,
                )

            rate = response.RatedShipment[0]
            charge = rate.TotalCharges

            # Some users are qualified to receive negotiated rates
            if (
                "NegotiatedRateCharges" in rate
                and rate.NegotiatedRateCharges
                and rate.NegotiatedRateCharges.TotalCharge.MonetaryValue
            ):
                charge = rate.NegotiatedRateCharges.TotalCharge

            return {
                "currency_code": charge.CurrencyCode,
                "price": charge.MonetaryValue,
            }

        except Fault as e:
            code = e.detail.xpath(
                "//err:PrimaryErrorCode/err:Code", namespaces=self.ns
            )[0].text
            description = e.detail.xpath(
                "//err:PrimaryErrorCode/err:Description", namespaces=self.ns
            )[0].text
            return self.get_error_message(code, description)
        except IOError as e:
            return self.get_error_message("0", "UPS Server Not Found:\n%s" % e)

    def send_shipping(
        self,
        shipment_info,
        packages,
        shipper,
        ship_from,
        ship_to,
        packaging_type,
        service_type,
        saturday_delivery,
        duty_payment,
        cod_info=None,
        access_point_id=None,
        access_point_country=None,
        access_point_phone=None,
        label_file_type="GIF",
        send_notification=False,
        send_notification_emails=None,
        uap_shipper_email=None,
        send_notification_undelivered_email=None,
        ups_carrier_account=False,
    ):
        if not packages:
            return {
                "error_message": "No packages",
            }
        client = self._set_client(self.SHIP_WSDL, "Ship", "ShipmentRequest")
        request = self.factory_ns3.RequestType()
        request.RequestOption = "nonvalidate"

        request_type = "shipping"
        label = self.factory_ns2.LabelSpecificationType()
        label.LabelImageFormat = self.factory_ns2.LabelImageFormatType()
        label.LabelImageFormat.Code = label_file_type
        label.LabelImageFormat.Description = label_file_type
        if label_file_type != "GIF":
            label.LabelStockSize = self.factory_ns2.LabelStockSizeType()
            label.LabelStockSize.Height = "6"
            label.LabelStockSize.Width = "4"

        shipment = self.factory_ns2.ShipmentType()
        if shipment_info.get("description"):
            shipment.Description = shipment_info["description"][:50]

        for package in self.set_package_detail(
            client, packages, packaging_type, ship_from, ship_to, cod_info, request_type
        ):
            shipment.Package.append(package)

        shipment.Shipper = self.factory_ns2.ShipperType()
        shipment.Shipper.Address = self.factory_ns2.ShipAddressType()
        shipment.Shipper.AttentionName = (shipper.name or "")[: self.NAME_LENGTH]
        shipment.Shipper.Name = (shipper.parent_id.name or shipper.name or "")[
            : self.NAME_LENGTH
        ]
        shipment.Shipper.Address.AddressLine = self.sanitize_addresses(
            [shipper.street, shipper.street2]
        )
        shipment.Shipper.Address.City = shipper.city or ""
        shipment.Shipper.Address.PostalCode = shipper.zip or ""
        shipment.Shipper.Address.CountryCode = shipper.country_id.code or ""
        if shipper.country_id.code in ("US", "CA"):
            shipment.Shipper.Address.StateProvinceCode = shipper.state_id.code or ""
        shipment.Shipper.ShipperNumber = self.shipper_number or ""
        shipment.Shipper.Phone = self.factory_ns2.ShipPhoneType()
        shipment.Shipper.Phone.Number = self._clean_phone_number(shipper.phone)

        shipment.ShipFrom = self.factory_ns2.ShipFromType()
        shipment.ShipFrom.Address = self.factory_ns2.ShipAddressType()
        shipment.ShipFrom.AttentionName = (ship_from.name or "")[: self.NAME_LENGTH]
        shipment.ShipFrom.Name = (ship_from.parent_id.name or ship_from.name or "")[
            : self.NAME_LENGTH
        ]
        shipment.ShipFrom.Address.AddressLine = self.sanitize_addresses(
            [ship_from.street, ship_from.street2]
        )
        shipment.ShipFrom.Address.City = ship_from.city or ""
        shipment.ShipFrom.Address.PostalCode = ship_from.zip or ""
        shipment.ShipFrom.Address.CountryCode = ship_from.country_id.code or ""
        if ship_from.country_id.code in ("US", "CA"):
            shipment.ShipFrom.Address.StateProvinceCode = ship_from.state_id.code or ""
        shipment.ShipFrom.Phone = self.factory_ns2.ShipPhoneType()
        shipment.ShipFrom.Phone.Number = self._clean_phone_number(ship_from.phone)

        shipment.ShipTo = self.factory_ns2.ShipToType()
        shipment.ShipTo.Address = self.factory_ns2.ShipToAddressType()
        shipment.ShipTo.AttentionName = (ship_to.name or "")[: self.NAME_LENGTH]
        shipment.ShipTo.Name = (ship_to.parent_id.name or ship_to.name or "")[
            : self.NAME_LENGTH
        ]
        shipment.ShipTo.Address.AddressLine = self.sanitize_addresses(
            [ship_to.street, ship_to.street2]
        )
        shipment.ShipTo.Address.City = ship_to.city or ""
        shipment.ShipTo.Address.PostalCode = ship_to.zip or ""
        shipment.ShipTo.Address.CountryCode = ship_to.country_id.code or ""
        if ship_to.country_id.code in ("US", "CA"):
            shipment.ShipTo.Address.StateProvinceCode = ship_to.state_id.code or ""
        if ship_to.country_id.code in ("IE"):
            shipment.ShipTo.Address.StateProvinceCode = ship_to.state_id.code or "--"
        shipment.ShipTo.Phone = self.factory_ns2.ShipPhoneType()
        shipment.ShipTo.Phone.Number = self._clean_phone_number(shipment_info["phone"])
        # if not ship_to.commercial_partner_id.is_company:
        #     shipment.ShipTo.Address.ResidentialAddressIndicator = None

        if send_notification:
            notification_dict = self._shipment_notification(
                access_point_id=access_point_id,
                access_point_country=access_point_country,
                access_point_phone=access_point_phone,
                send_notification_emails=send_notification_emails,
                uap_shipper_email=uap_shipper_email,
                send_notification_undelivered_email=send_notification_undelivered_email,
            )
            for key, value in notification_dict.items():
                setattr(shipment, key, value)
        else:
            if access_point_id:
                raise Exception(
                    "Sorry, notification sending is required when using Access Point"
                )
            shipment.ShipmentServiceOptions = ""

        shipment.Service = self.factory_ns2.ServiceType()
        shipment.Service.Code = service_type or ""
        shipment.Service.Description = "Service Code"
        if service_type == "96":
            shipment.NumOfPiecesInShipment = int(shipment_info.get("total_qty"))
        shipment.ShipmentRatingOptions = self.factory_ns2.RateInfoType()
        # shipment.ShipmentRatingOptions.NegotiatedRatesIndicator = None
        shipment.ShipmentRatingOptions.NegotiatedRatesIndicator = 1

        # Shipments from US to CA or PR require extra info
        if ship_from.country_id.code == "US" and ship_to.country_id.code in [
            "CA",
            "PR",
        ]:
            shipment.InvoiceLineTotal = self.factory_ns2.CurrencyMonetaryType()
            shipment.InvoiceLineTotal.CurrencyCode = shipment_info.get(
                "itl_currency_code"
            )
            shipment.InvoiceLineTotal.MonetaryValue = shipment_info.get(
                "ilt_monetary_value"
            )

        # set the default method for payment using shipper account
        payment_info = self.factory_ns2.PaymentInfoType()
        shipcharge = self.factory_ns2.ShipmentChargeType()
        shipcharge.Type = "01"

        # Bill Recevier 'Bill My Account'
        if ups_carrier_account:
            shipcharge.BillReceiver = self.factory_ns2.BillReceiverType()
            shipcharge.BillReceiver.Address = self.factory_ns2.BillReceiverAddressType()
            shipcharge.BillReceiver.AccountNumber = ups_carrier_account
            shipcharge.BillReceiver.Address.PostalCode = ship_to.zip
        else:
            shipcharge.BillShipper = self.factory_ns2.BillShipperType()
            shipcharge.BillShipper.AccountNumber = self.shipper_number or ""

        payment_info.ShipmentCharge = [shipcharge]

        if duty_payment == "SENDER":
            duty_charge = self.factory_ns2.ShipmentChargeType()
            duty_charge.Type = "02"
            duty_charge.BillShipper = self.factory_ns2.BillShipperType()
            duty_charge.BillShipper.AccountNumber = self.shipper_number or ""
            payment_info.ShipmentCharge.append(duty_charge)

        shipment.PaymentInformation = payment_info

        if saturday_delivery:
            if not shipment.ShipmentServiceOptions:
                shipment.ShipmentServiceOptions = (
                    self.factory_ns2.ShipmentServiceOptionsType()
                )
            shipment.ShipmentServiceOptions.SaturdayDeliveryIndicator = (
                saturday_delivery
            )
        self.shipment = shipment
        self.label = label
        self.request = request
        self.label_file_type = label_file_type

    def return_label(self):
        return_service = self.factory_ns2.ReturnServiceType()
        return_service.Code = "9"
        self.shipment.ReturnService = return_service
        for p in self.shipment.Package:
            p.Description = "Return of courtesy"

    def process_shipment(self):
        client = self._set_client(self.ship_wsdl, "Ship", "ShipmentRequest")
        service = self._set_service(client, "Ship")
        try:
            response = service.ProcessShipment(
                Request=self.request,
                Shipment=self.shipment,
                LabelSpecification=self.label,
            )

            # Check if shipment is not success then return reason for that
            if response.Response.ResponseStatus.Code != "1":
                ret = self.get_error_message(
                    response.Response.ResponseStatus.Code,
                    response.Response.ResponseStatus.Description,
                )
                ret["error_message"] = "%s\n\n%s\n\n%s\n\n%s" % (
                    ret["error_message"],
                    self.request,
                    self.shipment,
                    self.label,
                )
                return ret

            result = {}
            result["label_binary_data"] = {}
            for package in response.ShipmentResults.PackageResults:
                result["label_binary_data"][package.TrackingNumber] = self.save_label(
                    package.ShippingLabel.GraphicImage,
                    label_file_type=self.label_file_type,
                )
            result[
                "tracking_ref"
            ] = response.ShipmentResults.ShipmentIdentificationNumber
            result[
                "currency_code"
            ] = response.ShipmentResults.ShipmentCharges.TotalCharges.CurrencyCode

            # Some users are qualified to receive negotiated rates
            negotiated_rate = (
                "NegotiatedRateCharges" in response.ShipmentResults
                and response.ShipmentResults.NegotiatedRateCharges
                and response.ShipmentResults.NegotiatedRateCharges.TotalCharge.MonetaryValue
                or None
            )

            result["price"] = (
                negotiated_rate
                or response.ShipmentResults.ShipmentCharges.TotalCharges.MonetaryValue
            )
            return result

        except Fault as e:
            code = e.detail.xpath(
                "//err:PrimaryErrorCode/err:Code", namespaces=self.ns
            )[0].text
            description = e.detail.xpath(
                "//err:PrimaryErrorCode/err:Description", namespaces=self.ns
            )[0].text
            ret = self.get_error_message(code, description)
            ret["error_message"] = "%s\n\n%s\n\n%s\n\n%s\n\n%s" % (
                ret["error_message"],
                self.request,
                self.shipment,
                self.label,
                str(e),
            )
            return ret
        except IOError as e:
            return self.get_error_message("0", "UPS Server Not Found:\n%s" % e)

    def cancel_shipment(self, tracking_number):
        client = self._set_client(self.VOID_WSDL, "Void", "VoidShipmentRequest")
        service = self._set_service(client, "Void")

        request = self.factory_ns3.RequestType()
        request.TransactionReference = self.factory_ns3.TransactionReferenceType()
        request.TransactionReference.CustomerContext = "Cancle shipment"
        voidshipment = {"ShipmentIdentificationNumber": tracking_number or ""}

        result = {}
        try:
            response = service.ProcessVoid(Request=request, VoidShipment=voidshipment)
            if response.Response.ResponseStatus.Code == "1":
                return result
            return self.get_error_message(
                response.Response.ResponseStatus.Code,
                response.Response.ResponseStatus.Description,
            )

        except Fault as e:
            code = e.detail.xpath(
                "//err:PrimaryErrorCode/err:Code", namespaces=self.ns
            )[0].text
            description = e.detail.xpath(
                "//err:PrimaryErrorCode/err:Description", namespaces=self.ns
            )[0].text
            return self.get_error_message(code, description)
        except IOError as e:
            return self.get_error_message("0", "UPS Server Not Found:\n%s" % e)

    def _shipment_notification(
        self,
        access_point_id=None,
        access_point_country=None,
        access_point_phone=None,
        send_notification_emails=None,
        uap_shipper_email=None,
        send_notification_undelivered_email=None,
    ):
        client = self._set_client(self.SHIP_WSDL, "Ship", "ShipmentRequest")

        ret = {"ShipmentServiceOptions": self.factory_ns2.ShipmentServiceOptionsType()}

        if access_point_id and not access_point_country:
            raise Exception("UPS Access Point country is required")

        if not access_point_id and access_point_country:
            raise Exception(
                "UPS Access Point country given but access point ID not known"
            )

        if access_point_id:
            if not uap_shipper_email:
                raise Exception(
                    "UAP Shipper email is required when sending Access Point shipment"
                )

            notifications = []

            locator = UPSLocator(
                self.username,
                self.password,
                self.shipper_number,
                self.access_number,
                True,  # evil mode -- turn on production locator
            )
            access_point_res = locator.get_access_point(
                access_point_id, access_point_country
            )

            if access_point_res["status"] != "success":
                raise Exception("Could not find access point: %s" % access_point_res)

            access_point = access_point_res["result"]["AddressKeyFormat"]

            alternate_address = self.factory_ns2.AlternateDeliveryAddressType()

            alternate_address.Name = access_point.get(
                "CosigneeName", "<UPS Access Point>"
            )
            alternate_address.UPSAccessPointID = access_point_id
            alternate_address.Address = self.factory_ns2.ADLAddressType()
            alternate_address.Address.AddressLine = access_point["AddressLine"]
            alternate_address.Address.PostalCode = access_point.get(
                "PostcodePrimaryLow", access_point.get("PostalCode")
            )
            city = access_point.get("PoliticalDivision2")
            if city:
                alternate_address.Address.City = city
            state = access_point.get("PoliticalDivision1")
            if state:
                alternate_address.Address.StateProvinceCode = state
            alternate_address.Address.CountryCode = access_point["CountryCode"]
            ret["AlternateDeliveryAddress"] = alternate_address

            indication = self.factory_ns2.IndicationType()
            indication.Code = SHIPMENT_INDICATION_TYPES["access-point-delivery"]
            indication.Description = "DirectToRetail"
            ret["ShipmentIndicationType"] = indication

            # NOTIFICATIONS

            # 1. Notification about access point delivery is required (ADL Notification)
            notification = self._create_notification(
                client,
                "alternate-delivery-location",
                send_notification_emails,
                send_notification_undelivered_email,
            )
            # TODO: set according to partner's language
            # ENG/US, ENG/GB, NLD/97
            notification.Locale = self.factory_ns2.LocaleType()
            notification.Locale.Language = "ENG"
            notification.Locale.Dialect = "US"
            notifications.append(notification)

            # 2. Yet another notification that is required (UAP Shipper)
            notification = self._create_notification(
                client,
                "uap-shipper",
                uap_shipper_email,
                send_notification_undelivered_email,
            )
            # TODO: set according to partner's language
            # ENG/US, ENG/GB, NLD/97
            notification.Locale = self.factory_ns2.LocaleType()
            notification.Locale.Language = "ENG"
            notification.Locale.Dialect = "US"
            notifications.append(notification)

            # 3. qv-ship notification
            notification = self._create_notification(
                client,
                "qv-ship",
                send_notification_emails,
                send_notification_undelivered_email,
            )
            notifications.append(notification)

            ret["ShipmentServiceOptions"].Notification = notifications
        else:  # no access_point_id
            if not send_notification_emails:
                raise Exception(
                    "Send notification emails is empty but notification sending was requested"
                )

            notifications = []

            # 1. qv-ship notification (non UAP)
            notification = self._create_notification(
                client,
                "qv-ship",
                send_notification_emails,
                send_notification_undelivered_email,
            )
            # TODO: set according to partner's language
            # ENG/US, ENG/GB, NLD/97
            notification.Locale = self.factory_ns2.LocaleType()
            notification.Locale.Language = "ENG"
            notification.Locale.Dialect = "US"
            notifications.append(notification)

            # 2. qv-exception notification (non UAP)
            notification = self._create_notification(
                client, "qv-exception", send_notification_emails, None
            )
            notifications.append(notification)

            ret["ShipmentServiceOptions"].Notification = notifications

        return ret

    def _create_notification(self, client, code, emails, undelivered_emails):
        notification = self.factory_ns2.NotificationType()
        notification.NotificationCode = NOTIFICATION_CODES[code]

        email = self.factory_ns2.EmailDetailsType()
        email.EMailAddress = emails
        if undelivered_emails:
            email.UndeliverableEMailAddress = undelivered_emails
        notification.EMail = email

        return notification


class UPSLocator(object):
    PRODUCTION_URL = "https://onlinetools.ups.com/rest/Locator"
    TEST_URL = "https://wwwcie.ups.com/rest/Locator"

    # OptionType/OptionCode values
    OPTIONS = {
        "Location": {
            "type": "01",
            "codes": {
                "ups-access-point": "018",
            },
        },
        "RequestOption": {
            "all": "01",
            "access-point-search": "64",
        },
    }

    SAMPLE_UK_LOCATION = {
        "LocationID": "141577",
        "Geocode": {
            "Latitude": "51.47673797",
            "Longitude": "-0.11286599",
        },
        "AddressKeyFormat": {
            "ConsigneeName": "CALDWELL STORE",
            "AddressLine": "70 74 CALDWELL STREET",
            "PoliticalDivision2": "LONDON",
            "PostcodePrimaryLow": "SW9 0HB",
            "CountryCode": "GB",
        },
    }

    SAMPLE_US_LOCATION = {
        "LocationID": "80926",
        "Geocode": {
            "Latitude": "33.75909423",
            "Longitude": "-84.3829040",
        },
        "AddressKeyFormat": {
            "ConsigneeName": "THE UPS STORE",
            "AddressLine": "165 COURTLAND ST&#xD;STE A",
            "PoliticalDivision2": "ATLANTA",
            "PoliticalDivision1": "GA",
            "PostcodePrimaryLow": "30303",
            "CountryCode": "US",
        },
    }

    def __init__(
        self, username, password, shipper_number, access_number, prod_environment
    ):
        # Product and Testing url
        self.prod_environment = prod_environment

        # Basic detail require to authenticate
        self.username = username
        self.password = password
        self.shipper_number = shipper_number
        self.access_number = access_number

    @property
    def endurl(self):
        if self.prod_environment:
            return self.PRODUCTION_URL
        return self.TEST_URL

    def auth_data(self):
        return {
            "AccessRequest": {
                "AccessLicenseNumber": self.access_number,
                "UserId": self.username,
                "Password": self.password,
            },
        }

    def request_data(self, request_option="access-point-search"):
        return {
            "Request": {
                "RequestAction": "Locator",
                "RequestOption": self.OPTIONS["RequestOption"][request_option],
                "TransactionReference": {
                    "CustomerContext": "XOLT Sample Code",
                },
            },
            "Translate": {
                "Locale": "en_US",
            },
            "UnitOfMeasurement": {
                "Code": "KM",
            },
        }

    def request_body(self, data=None):
        """
        data:
            street
            political-division-1
            political-division-2
            political-division-3
            postal-code
            country-code
            latitude
            longitude
            search-radius
            maximum-list-size

        When passing address data, either of political-division-1 or
        political-division-2 is required.

        You can also pass only location-id, then request will query
        for that specific ID.
        """

        if not data:
            data = {}

        ret = {
            "LocatorRequest": {
                "OriginAddress": {
                    "PhoneNumber": "",
                    "AddressKeyFormat": {},
                    #    'AddressLine': data.get('street', '<street>'),
                    #    'PoliticalDivision1': data.get(
                    #        'political-division-1',
                    #        '<political-division-1>'
                    #    ),
                    #    'PoliticalDivision2': data.get(
                    #        'political-division-2',
                    #        '<political-division-2>'
                    #    ),
                    #    'PoliticalDivision3': data.get(
                    #        'political-division-3',
                    #        '<political-division-3>'
                    #    ),
                    #    'PostalCode': data.get(
                    #        'postal-code',
                    #        '<postal-code>'
                    #    ),
                    #    'CountryCode': data.get(
                    #        'country-code',
                    #        '<country-code>'
                    #    ),
                    # },
                    #'Geocode': {
                    #    'Latitude': xxx,
                    #    'Longitude': xxx,
                    # },
                },
                # NOTE: LocationSearchCriteria is needed only when
                #  RequestOption is set to 'all' == '1'
                "LocationSearchCriteria": {
                    "SearchOption": {
                        "OptionType": {
                            "Code": self.OPTIONS["Location"]["type"],
                        },
                        "OptionCode": {
                            "Code": self.OPTIONS["Location"]["codes"][
                                "ups-access-point"
                            ],
                        },
                    },
                },
                "MaximumListSize": data.get("maximum-list-size", "50"),
                "SearchRadius": data.get("search-radius", "50"),
            },
        }
        ret["LocatorRequest"].update(self.request_data())

        if "street" in data and "postal-code" in data and "country-code" in data:
            address_dict = {
                "AddressLine": data["street"],
                "PostalCode": data["postal-code"],
                "CountryCode": data["country-code"],
            }

            for x in range(1, 4):
                key = "political-division-%d" % x
                if key in data:
                    address_dict["PoliticalDivision%d" % x] = data[key]

            ret["LocatorRequest"]["OriginAddress"]["AddressKeyFormat"] = address_dict

        if "latitude" in data and "longitude" in data:
            ret["LocatorRequest"]["OriginAddress"]["Geocode"] = {
                "Latitude": data["latitude"],
                "Longitude": data["longitude"],
            }

        return ret

    def access_point_data(self, access_point_id, access_point_country):
        ret = self.auth_data()
        locator_request = {
            "LocatorRequest": {
                "LocationSearchCriteria": {
                    "AccessPointSearch": {
                        "AccesspointStatus": "01",
                        "PublicAccessPointID": access_point_id,
                    },
                },
                "OriginAddress": {
                    "PhoneNumber": "",
                    "AddressKeyFormat": {
                        "CountryCode": access_point_country,
                    },
                },
                "MaximumListSize": 15,
            },
        }
        ret.update(locator_request)
        ret["LocatorRequest"].update(self.request_data())

        return ret

    def get_access_point(self, access_point_id, access_point_country):
        request = self.access_point_data(access_point_id, access_point_country)

        res = requests.post(self.endurl, json=request)
        res_json = res.json()["LocatorResponse"]

        ret = {
            "status": "success",
            "result": {},
        }

        if res_json["Response"]["ResponseStatusDescription"] == "Failure":
            ret["status"] = "error"
            ret["error"] = res_json["Response"]["Error"]
            ret["request"] = res.request.body
            return ret

        if "SearchResults" in res_json:
            results = res_json["SearchResults"]
            if "DropLocation" in results:
                ret["result"] = results["DropLocation"]
            else:
                ret["status"] = "unknown-format"
                ret["unknown-format"] = res_json
        else:
            ret["status"] = "unknown-format"
            ret["unknown-format"] = res_json

        return ret

    def locate_access_point(self, data=None):
        request = self.auth_data()
        request.update(self.request_body(data=data))

        res = requests.post(self.endurl, json=request)
        res_json = res.json()["LocatorResponse"]

        ret = {
            "status": "success",
            "candidates": [],
            "results": [],
        }

        if res_json["Response"]["ResponseStatusDescription"] == "Failure":
            ret["status"] = "error"
            ret["error"] = res_json["Response"]["Error"]
            ret["request"] = res.request.body
            return ret

        if "SearchResults" in res_json:
            results = res_json["SearchResults"]
            if "DropLocation" in results:
                ret["results"] = results["DropLocation"]
            else:
                ret["candidates"] = results["GeocodeCandidate"]
        else:
            ret["status"] = "unknown-format"
            ret["unknown-format"] = res_json

        return ret

    def locate_access_point_candidate(self, candidate):
        """
        Calls self.locate_access_point with data taken from
        candidate AddressKeyFormat.
        """
        return self.locate_access_point(
            data=self.address_key_format_to_locate_data(candidate)
        )

    @staticmethod
    def address_key_format_to_locate_data(data):
        """
        Convert AddressKeyFormat to dict which is accepted by locate_access_point.
        """
        address_data = data["AddressKeyFormat"]
        geocode_data = data.get("Geocode", {})

        ret = {
            "street": address_data["AddressLine"],
            "postal_code": address_data.get(
                "PostcodePrimaryLow", address_data.get("PostalCode")
            ),
            "country-code": address_data["CountryCode"],
            "latitude": geocode_data.get("Latitude"),
            "longitude": geocode_data.get("Longitude"),
        }

        for x in range(1, 4):
            key = "PoliticalDivision%d" % x
            locate_key = "political-division-%d" % x
            if key in address_data:
                ret[locate_key] = address_data[key]

        return ret

    '''
    @staticmethod
    def create_ups_access_point(env, data):
        """
        data is of 'AccessPointInformation' type.
        env is needed to access the Odoo model.
        """
        address_data = data['AddressKeyFormat']
        geocode_data = data.get('Geocode', {})

        vals = {
            'location_id': data['LocationID'],
            'street': address_data['AddressLine'],
            'political_division_1': address_data.get('PoliticalDivision1', False),
            'political_division_2': address_data.get('PoliticalDivision2', False),
            'political_division_3': address_data.get('PoliticalDivision3', False),
            'postal_code': address_data.get('PostcodePrimaryLow', address_data.get('PostalCode')),
            'country_code': address_data['CountryCode'],
            'latitude': geocode_data.get('Latitude'),
            'longitude': geocode_data.get('Longitude'),
        }

        try:
            ap = env['delivery_ups.access_point'].search([
                ['location_id', '=', vals['location_id']]
            ])[0]
            print 'Updating with vals', vals
            ap.write(vals)
            return ap
        except IndexError:
            print 'Creating with vals', vals
            return env['delivery_ups.access_point'].create(vals)
    '''
