odoo.define("tameson_base.Session", function (require) {
  "use strict";

  var session = require("web.Session");
  var core = require("web.core");
  var _t = core._t;
  // Set `doy` for all locale to 4 days
  // ensures that week of the year according to ISO standard 4 days in january rule
  session.include({
    _configureLocale: function () {
      moment.updateLocale(moment.locale(), {
        week: {
          dow: (_t.database.parameters.week_start || 0) % 7,
          doy: 4,
        },
      });
    },
  });
});
