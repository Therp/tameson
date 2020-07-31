(function() {
  odoo.define('tameson_stock.list_view', function(require) {
    var FormController, ListController, Model, StockPicking;
    FormController = require('web.FormController');
    ListController = require('web.ListController');
    Model = require('web.BasicModel');
    StockPicking = new Model('stock.picking');
    FormController.include({
      renderButtons: function($node) {
        var ret;
        ret = this._super.apply(this, arguments);
        if (this.$buttons) {
          this.$buttons.on('click', '.batch-picking-ups-labels', this.batch_picking_ups_labels.bind(this));
        }
        return ret;
      },
      batch_picking_ups_labels: function() {
        var path, selected_ids, state, url;
        state = this.model.get(this.handle, {
          raw: true
        });
        selected_ids = state.data.picking_ids;
        path = "/stock/ups_labels/" + (selected_ids.join(","));
        url = location.protocol + "//" + location.host + path;
        return window.open(url, '_blank');
      }
    });
    return ListController.include({
      renderButtons: function($node) {
        var ret;
        ret = this._super.apply(this, arguments);
        this._buttonSelectionToggle();
        if (this.$buttons) {
          this.$buttons.on('click', '.picking-ups-labels', this.proxy('picking_ups_labels'));
        }
        return ret;
      },
      _onSelectionChanged: function(event) {
        var ret;
        ret = this._super.apply(this, arguments);
        this._buttonSelectionToggle();
        return ret;
      },
      _buttonSelectionToggle: function() {
        var $buttons;
        if (!this.$buttons) {
          return;
        }
        $buttons = this.$buttons.find('button.js-show-when-selected');
        if (this.selectedRecords.length === 0) {
          return $buttons.addClass('disabled');
        } else {
          return $buttons.removeClass('disabled');
        }
      },
      picking_ups_labels: function() {
        var path, r, selected_ids, url;
        selected_ids = (function() {
          var i, len, ref, results;
          ref = this.selectedRecords;
          results = [];
          for (i = 0, len = ref.length; i < len; i++) {
            r = ref[i];
            results.push(this.model.get(r).res_id);
          }
          return results;
        }).call(this);
        path = "/stock/ups_labels/" + (selected_ids.join(","));
        url = location.protocol + "//" + location.host + path;
        return window.open(url, '_blank');
      }
    });
  });

}).call(this);
