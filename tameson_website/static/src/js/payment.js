odoo.define("tameson_website.processing", function (require) {
  "use strict";

  var publicWidget = require("web.public.widget");
  var core = require("web.core");
  var _t = core._t;

  publicWidget.registry.PaymentForm.include({
    payEvent: function (ev) {
      var self = this;
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
  var PaymentProcessing = publicWidget.registry.PaymentProcessing;
  return PaymentProcessing.include({
    displayLoading: function () {
      var msg = _t("Processing, please wait ...");
      $.blockUI({
        message:
          '<h2 class="text-white"><img src="/web/static/src/img/spin.png" class="fa-pulse"/>' +
          "    <br />" +
          msg +
          "</h2>",
      });
    },
  });
});
