frappe.ui.form.on("Api Controller", {
    refresh(frm) {

        frm.add_custom_button("Test Connection", function () {

            frappe.call({
                method: "ai_erpnext.ai_erpnext.doctype.api_controller.api_controller.test_ai_connection",
                callback: function(r) {

                    if (r.message.success) {

                        frappe.msgprint({
                            title: "Success",
                            message: r.message.message,
                            indicator: "green"
                        });

                    } else {

                        frappe.msgprint({
                            title: "Failed",
                            message: r.message.message,
                            indicator: "red"
                        });

                    }
                }
            });

        });

    }
});