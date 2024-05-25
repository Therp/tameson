###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo.http import Controller, request, route


class RMA(Controller):
    @route("/rma/apply", type="http", auth="public", website=True, sitemap=True)
    def rma_apply(self, **kw):
        partner = request.env.user.partner_id
        if request.httprequest.method == "POST":
            if request.env.user._is_public():
                email = request.params["email"]
                partner = (
                    request.env["res.partner"]
                    .sudo()
                    .search([("email", "=", email)], order="parent_id DESC", limit=1)
                )
            headers = ["product", "qty"]
            table = []
            first_so = request.params["order"]
            so = (
                request.env["sale.order"]
                .sudo()
                .search(
                    [("name", "=", first_so)],
                    limit=1,
                )
            ).id
            first_sku = request.params["1-product"]
            sku = (
                request.env["product.product"]
                .sudo()
                .search([("default_code", "=", first_sku)], limit=1)
                .id
            )
            for i in range(1, 6):
                vals = [request.params["%d-%s" % (i, h)] for h in headers]
                if any(vals):
                    table.append(vals)
            rproducts = "\n".join(
                ["SKU: %s, Quantity: %s" % tuple(row) for row in table]
            )
            reason = request.params["return-reason"]
            iban = request.params["iban"]
            substance = request.params["substance"]
            description = """Reason for return: %s
Order: %s
Products:
%s
Application substance: %s
IBAN account number: %s""" % (
                reason,
                first_so,
                rproducts,
                substance,
                iban,
            )
            if request.env.user._is_public():
                description = "Email: %s\nName: %s\nCompany: %s\nAddress:\n%s\n%s" % (
                    email,
                    request.params["name"],
                    request.params["company"],
                    request.params["address"],
                    description,
                )
            if table:
                ticket = (
                    request.env["helpdesk.ticket"]
                    .sudo()
                    .create(
                        {
                            "partner_id": partner.id,
                            "description": description,
                            "team_id": 1,
                            "name": "%s - %s - %s"
                            % (first_so, first_sku, partner.name),
                            "sale_order_id": so,
                            "product_id": sku,
                        }
                    )
                )
                ticket.message_post_with_view(
                    "tameson_helpdesk.rma_data_table",
                    values={"headers": headers, "table": table},
                    message_type="comment",
                    subtype_id=1,
                )
                return request.render(
                    "tameson_helpdesk.rma_application_success", {"ticket": ticket}
                )
        SaleOrder = request.env["sale.order"]
        domain = [
            ("message_partner_ids", "child_of", [partner.commercial_partner_id.id]),
            ("state", "in", ["sale", "done"]),
        ]
        orders = SaleOrder.sudo().search(domain, order="date_order desc")
        products = (
            orders.sudo()
            .mapped("order_line.product_id.product_tmpl_id")
            .filtered(lambda p: p.type == "product")
        )
        return request.render(
            "tameson_helpdesk.rma_application",
            {"orders": orders, "products": products},
        )
