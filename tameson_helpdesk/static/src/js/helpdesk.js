odoo.define("tameson_helpdesk.rma", function (require) {
    "use strict";
    require('web.dom_ready');
    document.querySelector('#rma-order').addEventListener('input', onInputRmaOrder);
    function onInputRmaOrder(e) {
        var input = e.target,
            val = input.value;
        var list = input.getAttribute('list'),
            options = document.getElementById(list).childNodes;
        var setOptions = function (newOptions, element) {
            element.innerHTML = "";
            newOptions.forEach((item => {
                let option = document.createElement('option');
                option.textContent = item[1];
                option.value = item[0];
                element.appendChild(option);
            }))
        }
        for (var i = 0; i < options.length; i++) {
            if (options[i].value === val) {
                var skus = JSON.parse(options[i].getAttribute('skus'));
                [...Array(5).keys()].forEach(i => {
                    setOptions(skus, document.getElementById(`${i + 1}-products`));
                })
                return;
            }
        }
        let all_skus = JSON.parse(document.getElementById('rma-order').getAttribute('skus'));
        [...Array(5).keys()].forEach(i => {
            setOptions(all_skus, document.getElementById(`${i + 1}-products`));
        })
    }
});
