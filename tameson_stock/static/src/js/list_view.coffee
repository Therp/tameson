odoo.define 'tameson_stock.list_view', (require) ->
    FormController = require 'web.FormController'
    ListController = require 'web.ListController'
    rpc = require 'web.rpc'

    FormController.include
        renderButtons: ($node) ->
            ret = @_super.apply this, arguments

            if @$buttons
                @$buttons.on 'click', '.batch-picking-ups-labels', @batch_picking_ups_labels.bind(this)
                @$buttons.on 'click', '.batch-picking-delivery-labels', @batch_picking_delivery_labels.bind(this)

            ret

        batch_picking_ups_labels: () ->
            state = @model.get(@handle, {raw: true})
            selected_ids = state.data.picking_ids
            path = "/stock/ups_labels/#{selected_ids.join(",")}"
            url = "#{location.protocol}//#{location.host}#{path}"
            window.open url, '_blank'

        batch_picking_delivery_labels: () ->
            state = @model.get(@handle, {raw: true})
            selected_ids = state.data.picking_ids
            rpc.query(
              model: 'stock.picking'
              method: 'search_read'
              args: [
                  [['id', 'in', selected_ids],
                   ['state', 'not in', ['draft', 'cancel']]],
                  ['id']
                  ]
            ).then (objs) ->
                ids = (i.id for i in objs)
                path = "/stock/delivery_labels/#{ids.join(",")}"
                url = "#{location.protocol}//#{location.host}#{path}"
                window.open url, '_blank'

    ListController.include
        renderButtons: ($node) ->
            ret = @_super.apply this, arguments

            @_buttonSelectionToggle()

            if @$buttons
                @$buttons.on 'click', '.picking-ups-labels', @proxy('picking_ups_labels')
                @$buttons.on 'click', '.picking-delivery-labels', @proxy('picking_delivery_labels')

            ret

        _onSelectionChanged: (event) ->
            ret = @_super.apply this, arguments

            @_buttonSelectionToggle()

            ret

        _buttonSelectionToggle: () ->
            if not @$buttons
                return

            $buttons = @$buttons.find 'button.js-show-when-selected'
            if @selectedRecords.length == 0
                $buttons.addClass 'disabled'
            else
                $buttons.removeClass 'disabled'

        picking_ups_labels: () ->
            selected_ids = (@model.get(r).res_id for r in @selectedRecords)
            path = "/stock/ups_labels/#{selected_ids.join(",")}"
            url = "#{location.protocol}//#{location.host}#{path}"
            window.open url, '_blank'

        picking_delivery_labels: () ->
            selected_ids = (@model.get(r).res_id for r in @selectedRecords)
            path = "/stock/delivery_labels/#{selected_ids.join(",")}"
            url = "#{location.protocol}//#{location.host}#{path}"
            window.open url, '_blank'
