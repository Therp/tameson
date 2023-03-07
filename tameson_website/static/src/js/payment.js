odoo.define("tameson_website.processing", function (require) {
  "use strict";

  var publicWidget = require("web.public.widget");
  var core = require("web.core");
  var _t = core._t;

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
