odoo.define("tameson_website.processing", function (require) {
    "use strict";

    var publicWidget = require("web.public.widget");

    publicWidget.registry.PaymentCheckoutForm.include({
        _onClickPay: function (ev) {
            ev.preventDefault();
            if ($("#po-reference").length > 0) {
                const po_ref = $("#po-reference")[0].value;
                if (po_ref) {
                    this._rpc({
                        route: "/set/po_reference",
                        params: {
                            po_reference: po_ref,
                        },
                    });
                }
            }
            return this._super.apply(this, arguments);
        },
    });
});
