odoo.define('tameson_po_lines_clipboard.clipboardbutton', function (require) {
	var FormController = require('web.FormController');
	var core = require("web.core");
	var _t = core._t;

	var POClipboardButton = FormController.include({
		_onButtonClicked: function (event) {
		if(event.data.attrs.name === "tameson_po_copy_clipboard"){
			var textarea = document.createElement("textarea");
			var text_to_copy = ''
			if (document.getElementsByName("clipboard_text_handle").length > 0) {
				var text_to_copy = document.getElementsByName("clipboard_text_handle")[0].textContent;
			}
			textarea.textContent = text_to_copy;
			textarea.style.position = "fixed";
			document.body.appendChild(textarea);
			textarea.select();
			try {
				return document.execCommand("copy");  // Security exception may be thrown by some browsers.
			}
			catch (ex) {
				console.warn("Copy to clipboard failed.", ex);
				return false;
			}
			finally {
				document.body.removeChild(textarea);
				this.do_notify(
                    _t("Done!"),
                    _t("PO lines copied to clipboard.")
                );
			}
		}
			this._super(event);
		},
	});
	return POClipboardButton;
});