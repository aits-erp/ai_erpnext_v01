frappe.ui.form.on(frappe.get_route()[1] || 'Quotation', {
    refresh: function(frm) {
        // Show "View Source Email" if linked
        frm.add_custom_button('📧 View Source Email', function() {
            frappe.set_route('ai_email_inbox');
        }, '🤖 AI');

        // Show "Process New Document" always
        frm.add_custom_button('📄 Process Document', function() {
            frappe.set_route('ai_document_processor');
        }, '🤖 AI');
    }
});