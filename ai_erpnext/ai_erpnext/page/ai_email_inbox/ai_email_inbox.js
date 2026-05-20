frappe.pages['ai_email_inbox'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: '📧 AI Email Inbox',
        single_column: true
    });

    page.add_button('🔄 Refresh', function() { load_inbox(); });
    page.add_button('⚙️ Email Settings', function() {
        frappe.set_route('List', 'Email Account');
    });

    inject_inbox_styles();
    render_inbox(wrapper);
    load_inbox();
    setInterval(load_inbox, 30000);
};

function render_inbox(wrapper) {
    $(wrapper).find('.layout-main-section').html(`
        <div class="inbox-root">

            <!-- Stats Bar -->
            <div class="inbox-stats" id="inbox-stats">
                <div class="stat-card" id="stat-pending">
                    <div class="stat-num">0</div>
                    <div class="stat-label">Pending</div>
                </div>
                <div class="stat-card" id="stat-processed">
                    <div class="stat-num">0</div>
                    <div class="stat-label">Processed Today</div>
                </div>
                <div class="stat-card" id="stat-ignored">
                    <div class="stat-num">0</div>
                    <div class="stat-label">Ignored</div>
                </div>
            </div>

            <!-- Filter Bar -->
            <div class="inbox-filters">
                <button class="filter-btn active" data-status="Pending">
                    🕐 Pending
                </button>
                <button class="filter-btn" data-status="Processed">
                    ✅ Processed
                </button>
                <button class="filter-btn" data-status="Ignored">
                    🗑️ Ignored
                </button>
                <button class="filter-btn" data-status="All">
                    📋 All
                </button>
                <button class="delete-selected-btn">
                🗑 Delete Selected
               </button>
               
                <input type="text" id="inbox-search"
                    placeholder="🔍 Search by subject or sender..."
                    class="inbox-search">

                    
            </div>

            <!-- Email List -->
            <div id="inbox-loading" class="inbox-loading">
                <div class="ai-spinner"></div> Loading emails...
            </div>
            <div id="inbox-empty" class="inbox-empty" style="display:none">
                <div style="font-size:48px">📭</div>
                <div>No emails found</div>
                <div class="inbox-empty-sub">
                    Make sure Email Account is configured and set to fetch
                </div>
            </div>
            <div id="inbox-list" style="display:none"></div>
            <div id="pagination-bar" class="pagination-bar"></div>

        </div>

        <!-- Review Modal -->
        <div id="inbox-modal-overlay" class="modal-overlay" style="display:none">
            <div class="inbox-modal">
                <div class="inbox-modal-header">
                    <div>
                        <div id="imodal-subject" class="imodal-subject"></div>
                        <div id="imodal-meta" class="imodal-meta"></div>
                    </div>
                    <button onclick="close_inbox_modal()" class="modal-close">✕</button>
                </div>
                <div class="inbox-modal-body">

                    <!-- Tabs inside modal -->
                    <div class="imodal-tabs">
                        <button class="imodal-tab active" data-tab="extracted">
                            📊 Extracted Data
                        </button>
                        <button class="imodal-tab" data-tab="raw">
                            📧 Original Email
                        </button>
                    </div>

                    <!-- Extracted Tab -->
                    <div class="imodal-tab-content active" id="imodal-extracted">
                        <div class="ai-summary-grid" id="imodal-summary"></div>
                        <div class="section-label" style="margin-top:14px">
                            Line Items
                        </div>
                        <div class="ai-table-wrap">
                            <table class="ai-table">
                                <thead>
                                    <tr>
                                        <th>Item</th>
                                        <th>Qty</th>
                                        <th>Rate</th>
                                        <th>Amount</th>
                                        <th>UOM</th>
                                    </tr>
                                </thead>
                                <tbody id="imodal-items"></tbody>
                            </table>
                        </div>

                        <!-- Notes -->
                        <div id="imodal-notes-wrap" style="display:none">
                            <div class="section-label" style="margin-top:14px">
                                Notes / Terms
                            </div>
                            <div id="imodal-notes" class="imodal-notes-box"></div>
                        </div>
                    </div>

                    <!-- Raw Email Tab -->
                    <div class="imodal-tab-content" id="imodal-raw">
                        <div class="imodal-raw-box" id="imodal-raw-content">
                            Loading...
                        </div>
                    </div>

                    <!-- Action Section -->
                    <div class="section-label" style="margin-top:18px">
                        ⚡ Create Document
                    </div>
                    <div class="action-grid" id="imodal-actions"></div>

                    <!-- Loading + Result -->
                    <div id="imodal-loading" class="inbox-loading" style="display:none">
                        <div class="ai-spinner"></div> Creating in ERPNext...
                    </div>
                    <div id="imodal-result" class="imodal-result" style="display:none">
                        <strong>✅ Created Successfully</strong>
                        <div id="imodal-result-links"></div>
                    </div>
                </div>
            </div>
        </div>
    `);

    // Filter buttons
    $(wrapper).on('click', '.filter-btn', function() {
        $('.filter-btn').removeClass('active');
        $(this).addClass('active');
        _current_filter = $(this).data('status');
        load_inbox();
    });
   // Delete selected emails
$(wrapper).on('click', '.delete-selected-btn', function() {

    if (selected_emails.length === 0) {
        frappe.msgprint('Select emails first');
        return;
    }

    frappe.confirm(
        `Delete ${selected_emails.length} emails permanently?`,
        function() {

            frappe.call({
                method: 'ai_erpnext.api.delete_email_queue_items',
                args: {
                    names: selected_emails
                },
                callback: function(r) {

                    if (r.message.success) {

                        frappe.show_alert({
                            message: 'Emails deleted',
                            indicator: 'green'
                        });

                        selected_emails = [];

selection_mode = false;

$('#pagination-bar').html('');

load_inbox();
                    }

                }
            });

        }
    );

});
// Toggle selection mode
$(wrapper).on('click', '.select-mode-btn', function() {

    selection_mode = !selection_mode;

    if (!selection_mode) {
        selected_emails = [];
    }

    load_inbox();
});
    // Search
    var search_timer;
    $('#inbox-search').on('input', function() {
        clearTimeout(search_timer);
        search_timer = setTimeout(load_inbox, 400);
    });
        // Email selection
$(wrapper).on('change', '.email-checkbox', function() {

    var name = $(this).data('name');

    if ($(this).is(':checked')) {

        if (!selected_emails.includes(name)) {
            selected_emails.push(name);
        }

    } else {

        selected_emails =
            selected_emails.filter(x => x !== name);

    }

});
    // Modal inner tabs
    $(wrapper).on('click', '.imodal-tab', function() {
        var tab = $(this).data('tab');
        $('.imodal-tab').removeClass('active');
        $('.imodal-tab-content').removeClass('active');
        $(this).addClass('active');
        $(`#imodal-${tab}`).addClass('active');
    });
}
var _current_page = 1;
var _page_length = 20;
var _current_filter = 'Pending';
var _current_item = null;
var selected_emails = [];
var selection_mode = false;

function load_inbox() {
    $('#inbox-loading').show();
    $('#inbox-list').hide();
    $('#inbox-empty').hide();

    var search = $('#inbox-search').val() || '';
    var status = _current_filter === 'All' ? '' : _current_filter;

    frappe.call({
        method: 'ai_erpnext.api.get_email_queue',
       args: {
              status: status,
               search: search,
              page: _current_page,
               page_length: _page_length
             },
        callback: function(r) {
            $('#inbox-loading').hide();
            if (!r.message || !r.message.success) return;

            var items = r.message.items || [];
            var counts = r.message.counts || {};

            // Update stats
            $('#stat-pending .stat-num').text(counts.pending || 0);
            $('#stat-processed .stat-num').text(counts.processed_today || 0);
            $('#stat-ignored .stat-num').text(counts.ignored || 0);

            if (items.length === 0) {
                $('#inbox-empty').show();
                return;
            }

            var html = items.map(function(item) {
                var status_class = {
                    'Pending': 'status-pending',
                    'Processed': 'status-processed',
                    'Ignored': 'status-ignored'
                }[item.status] || '';

                var status_icon = {
                    'Pending': '🕐',
                    'Processed': '✅',
                    'Ignored': '🗑️'
                }[item.status] || '';

                return `
                <div class="inbox-row" data-queue="${item.name}">
                 ${selection_mode ? `
<input type="checkbox"
    class="email-checkbox"
    data-name="${item.name}">
` : ''}
                    <div class="inbox-row-left">
                        <div class="inbox-row-subject">
                            ${item.email_subject || '(No subject)'}
                        </div>
                        <div class="inbox-row-meta">
                            📤 ${item.from_email || '—'} &nbsp;·&nbsp;
                            🕐 ${frappe.datetime.str_to_user(item.received_on)}
                            ${item.created_document ?
                                `&nbsp;·&nbsp; 📄 ${item.created_document}` : ''}
                        </div>
                    </div>
                    <div class="inbox-row-right">
                        <span class="dtype-chip">${item.suggested_doctype || '?'}</span>
                        <span class="status-chip ${status_class}">
                            ${status_icon} ${item.status}
                        </span>
                        ${item.status === 'Pending' ? `
                        <button class="ai-btn ai-btn-primary ai-btn-sm"
                            onclick="open_inbox_modal('${item.name}')">
                            Review →
                        </button>
                        <button class="ai-btn ai-btn-ghost ai-btn-sm"
                            onclick="quick_ignore('${item.name}')">
                            Ignore
                        </button>` : `
                        <button class="ai-btn ai-btn-ghost ai-btn-sm"
                            onclick="open_inbox_modal('${item.name}')">
                            View
                        </button>`}
                    </div>
                </div>`;
            }).join('');

            $('#inbox-list').html(html).show();
            render_pagination(r.message.pagination);
        }
    });
}
function render_pagination(pagination) {

    if (!pagination) return;

    var html = `
        <button class="page-btn"
            ${pagination.page <= 1 ? 'disabled' : ''}
            onclick="change_page(${pagination.page - 1})">
            ← Prev
        </button>

        <span class="page-info">
            Page ${pagination.page} of ${pagination.total_pages}
        </span>

        <button class="page-btn"
            ${pagination.page >= pagination.total_pages ? 'disabled' : ''}
            onclick="change_page(${pagination.page + 1})">
            Next →
        </button>
        <button class="page-btn select-mode-btn">
    ${selection_mode ? 'Cancel' : 'Select'}
</button>
    `;

    $('#pagination-bar').html(html);
}


function change_page(page) {

    _current_page = page;

    load_inbox();

}
function open_inbox_modal(queue_name) {
    frappe.call({
        method: 'ai_erpnext.api.get_queue_item_detail',
        args: { queue_name: queue_name },
        callback: function(r) {
            if (!r.message || !r.message.success) return;
            var d = r.message.data;
            // _current_item = d;
            // _current_item.extracted._queue_name = queue_name;
            _current_item = d;
            _current_queue_name = queue_name;

            $('#imodal-subject').text(d.email_subject || '(No subject)');
            $('#imodal-meta').text(
                'From: ' + d.from_email + '  ·  ' + d.received_on
            );
            $('#imodal-loading').hide();
            $('#imodal-result').hide();

            // Summary
            var ext = d.extracted;
            var party = ext.customer_name || ext.supplier_name || '—';
            $('#imodal-summary').html(`
                <div class="ai-sum-card">
                    <div class="ai-sum-label">Type</div>
                    <div class="ai-sum-val">${ext.document_type || '—'}</div>
                </div>
                <div class="ai-sum-card">
                    <div class="ai-sum-label">Party</div>
                    <div class="ai-sum-val">${party}</div>
                </div>
                <div class="ai-sum-card">
                    <div class="ai-sum-label">Date</div>
                    <div class="ai-sum-val">${ext.document_date || '—'}</div>
                </div>
                <div class="ai-sum-card">
                    <div class="ai-sum-label">Total</div>
                    <div class="ai-sum-val">
                        ${ext.currency || 'INR'} ${ext.grand_total || '—'}
                    </div>
                </div>
            `);

            // Items
            var rows = (ext.items || []).map(function(i) {
                return `<tr>
                    <td>${i.item_name || '—'}</td>
                    <td>${i.qty || 1}</td>
                    <td>${i.rate || 0}</td>
                    <td>${i.amount || 0}</td>
                    <td>${i.uom || 'Nos'}</td>
                </tr>`;
            }).join('');
            $('#imodal-items').html(rows ||
                '<tr><td colspan="5" style="text-align:center;color:#aaa">No items</td></tr>'
            );

            // Notes
            if (ext.notes) {
                $('#imodal-notes').text(ext.notes);
                $('#imodal-notes-wrap').show();
            }

            // Raw email
            // $('#imodal-raw-content').text(d.email_body || '(Email body not stored)');
            $('#imodal-raw-content').html(d.email_body || '<em style="color:#aaa">(Email body not stored)</em>');

            // Actions
            var doc_type = (ext.document_type || "").toLowerCase();

            // Define allowed actions per detected document type
            var actions = [];

            if (doc_type.includes("purchase invoice")) {
                actions = [
                    {a:'pi_only', l:'🧾 Purchase Invoice Only', c:'#4CAF50'}
                ];
            } else if (doc_type.includes("purchase order")) {
                actions = [
                    {a:'po_only',  l:'📦 Purchase Order Only',          c:'#2196F3'},
                    {a:'pi_only',  l:'🧾 Purchase Invoice Only',         c:'#4CAF50'},
                    {a:'po_to_pi', l:'📦 → 🧾 PO + Purchase Invoice',   c:'#FF9800'}
                ];
            } else if (doc_type.includes("sales invoice")) {
                actions = [
                    {a:'si_only', l:'🧾 Sales Invoice Only', c:'#4CAF50'}
                ];
            } else if (doc_type.includes("sales order")) {
                actions = [
                    {a:'so_only',        l:'📦 Sales Order Only',       c:'#2196F3'},
                    {a:'si_only',        l:'🧾 Sales Invoice Only',      c:'#4CAF50'},
                    {a:'so_to_si',       l:'📦 → 🧾 SO + Invoice',      c:'#FF9800'}
                ];
            } else {
                // Quotation or unknown — show full sales chain
                actions = [
                    {a:'quotation_only',  l:'📋 Quotation Only',              c:'#7c6fcd'},
                    {a:'so_only',         l:'📦 Sales Order Only',            c:'#2196F3'},
                    {a:'si_only',         l:'🧾 Sales Invoice Only',          c:'#4CAF50'},
                    {a:'quotation_to_so', l:'📋 → 📦 Quotation + SO',        c:'#FF9800'},
                    {a:'quotation_so_si', l:'📋 → 📦 → 🧾 Full Chain',       c:'#F44336'}
                ];
            }

            // Show detected type warning if mismatch
            var warning = "";
            if (doc_type.includes("invoice") && actions.length === 1) {
                warning = `<div style="background:#fff3e0;border-left:4px solid #FF9800;
                    padding:8px 12px;border-radius:4px;font-size:12px;margin-bottom:10px;color:#666">
                    ⚠️ Detected as <strong>${ext.document_type}</strong> — 
                    only relevant actions are shown
                </div>`;
            }

            var btns = actions.map(function(x) {
                return `<button class="action-choice-btn"
                    style="border-left:4px solid ${x.c}"
                    onclick="inbox_create('${x.a}','${queue_name}')">
                    ${x.l}
                </button>`;
            }).join('');

            if (d.status === 'Processed') {
                $('#imodal-actions').html(
                    `<div style="color:#888;font-size:13px">
                        Already processed: ${d.created_document || ''}
                    </div>`
                );
            } else {
                $('#imodal-actions').html(warning + btns);
            }

            // Only show if items are empty or missing HSN
            var has_hsn = (d.extracted.items || []).every(i => i.hsn_code);
            var has_items = (d.extracted.items || []).length > 0;

            if (!has_items || !has_hsn) {
                $('#imodal-actions').prepend(`
                    <div style="width:100%; margin-bottom:12px; padding:10px; 
                        background:#fff8e1; border-radius:6px; border-left:4px solid #ffc107;">
                        <div style="font-size:12px; color:#666; margin-bottom:8px;">
                            ⚠️ ${!has_items ? 'No items extracted.' : 'HSN codes missing.'} 
                            Re-extract with updated AI prompt:
                        </div>
                        <button class="ai-btn ai-btn-primary ai-btn-sm" 
                            id="reextract-btn" onclick="reextract_item('${queue_name}')">
                            🔄 Re-extract with AI
                        </button>
                    </div>
                `);
            }

            $('#inbox-modal-overlay').show();
        }
    });
}

function inbox_create(action, queue_name) {
    if (!_current_item) return;
    $('#imodal-actions').find('button').prop('disabled', true);
    $('#imodal-loading').show();

    frappe.call({
        method: 'ai_erpnext.api.create_from_extracted',
        args: {
            extracted_data_json: JSON.stringify(_current_item.extracted),
            action: action
        },
        callback: function(r) {
            $('#imodal-loading').hide();
            if (r.message && r.message.success) {
                var links = (r.message.created || []).map(function(d) {
                    var url = '/app/' +
                        d.doctype.toLowerCase().replace(/ /g,'-') +
                        '/' + encodeURIComponent(d.name);
                    return `<a href="${url}" target="_blank" class="result-link">
                        ${d.doctype}: ${d.name} →
                    </a>`;
                }).join('');
                $('#imodal-result-links').html(links);
                $('#imodal-result').show();

                frappe.call({
                    method: 'ai_erpnext.api.mark_queue_processed',
                    args: {
                        queue_name: _current_queue_name, //changed from queue_name to _current_queue_name
                        created_document: r.message.created[0].name
                    }
                });
                setTimeout(function() {
                    close_inbox_modal();
                    load_inbox();
                }, 2500);
            } else {
                frappe.show_alert({
                    message: (r.message && r.message.error) || 'Failed',
                    indicator: 'red'
                });
                $('#imodal-actions').find('button').prop('disabled', false);
            }
        }
    });
}

function close_inbox_modal() {
    $('#inbox-modal-overlay').hide();
    _current_item = null;
}

function quick_ignore(queue_name) {
    frappe.call({
        method: 'ai_erpnext.api.ignore_queue_item',
        args: { queue_name: queue_name },
        callback: function() {
            frappe.show_alert({ message: 'Ignored', indicator: 'orange' });
            load_inbox();
        }
    });
}

function reextract_item(queue_name) {
    $('#reextract-btn').prop('disabled', true).text('⏳ Extracting...');
    frappe.call({
        method: 'ai_erpnext.api.reextract_queue_item',
        args: { queue_name: queue_name },
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.show_alert({message: 'Re-extracted successfully', indicator: 'green'});
                // Reload the modal with fresh data
                close_inbox_modal();
                setTimeout(function() { open_inbox_modal(queue_name); }, 300);
            } else {
                frappe.show_alert({
                    message: (r.message && r.message.error) || 'Failed',
                    indicator: 'red'
                });
                $('#reextract-btn').prop('disabled', false).text('🔄 Re-extract with AI');
            }
        }
    });
}

function inject_inbox_styles() {
    $('<style>').text(`
        .inbox-root { max-width:960px; margin:0 auto; padding:20px; }
        .inbox-stats { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:20px; }
        .stat-card { background:#fff; border:1px solid #eee; border-radius:10px; padding:16px; text-align:center; box-shadow:0 1px 4px rgba(0,0,0,0.04); }
        .stat-num { font-size:28px; font-weight:800; color:#5e64ff; }
        .stat-label { font-size:12px; color:#aaa; margin-top:4px; }
        .inbox-filters { display:flex; align-items:center; gap:8px; margin-bottom:16px; flex-wrap:wrap; }
        .filter-btn { padding:7px 16px; border-radius:20px; border:1px solid #e0e0e0; background:#fff; cursor:pointer; font-size:13px; color:#666; transition:all 0.15s; }
        .filter-btn.active { background:#5e64ff; color:#fff; border-color:#5e64ff; }
         .delete-selected-btn {
    background:#f5f5f5;
    color:#333;
    border:1px solid #ddd;
           color:grey;
          border:none;
            padding:7px 16px;
           border-radius:20px;
           cursor:pointer;
         font-size:13px;
               font-weight:600;
}
        .inbox-search { margin-left:auto; padding:7px 14px; border-radius:20px; border:1px solid #e0e0e0; font-size:13px; width:240px; outline:none; }
        .inbox-loading { display:flex; align-items:center; gap:10px; color:#888; padding:30px 0; }
        .inbox-empty { text-align:center; padding:60px; color:#bbb; }
        .inbox-empty-sub { font-size:12px; margin-top:6px; }
        .inbox-row { display:flex; align-items:center; justify-content:space-between; background:#fff; border:1px solid #eee; border-radius:8px; padding:14px 16px; margin-bottom:8px; transition:box-shadow 0.15s; gap:12px; }
        .inbox-row:hover { box-shadow:0 2px 8px rgba(0,0,0,0.07); }
        .inbox-row-left { flex:1; min-width:0; }
        .inbox-row-subject { font-weight:600; color:#333; font-size:14px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .inbox-row-meta { font-size:12px; color:#aaa; margin-top:4px; }
        .inbox-row-right { display:flex; align-items:center; gap:8px; flex-shrink:0; }
        .dtype-chip { background:#e8eaff; color:#5e64ff; border-radius:12px; padding:3px 10px; font-size:12px; font-weight:600; }
        .status-chip { border-radius:12px; padding:3px 10px; font-size:12px; font-weight:600; }
        .status-pending { background:#fff8e1; color:#f57f17; }
        .status-processed { background:#e8f5e9; color:#2e7d32; }
        .status-ignored { background:#f5f5f5; color:#999; }
        .modal-overlay { position:fixed; inset:0; background:rgba(0,0,0,0.55); z-index:9999; display:flex; align-items:center; justify-content:center; padding:20px; }
        .inbox-modal { background:#fff; border-radius:14px; width:100%; max-width:700px; max-height:90vh; overflow-y:auto; box-shadow:0 24px 80px rgba(0,0,0,0.25); }
        .inbox-modal-header { display:flex; justify-content:space-between; align-items:flex-start; padding:18px 20px; border-bottom:1px solid #eee; }
        .imodal-subject { font-weight:700; font-size:15px; color:#1a1a2e; }
        .imodal-meta { font-size:12px; color:#aaa; margin-top:4px; }
        .modal-close { background:none; border:none; font-size:20px; cursor:pointer; color:#bbb; line-height:1; }
        .inbox-modal-body { padding:20px; }
        .imodal-tabs { display:flex; gap:4px; margin-bottom:16px; border-bottom:2px solid #f0f0f0; }
        .imodal-tab { background:none; border:none; padding:8px 16px; font-size:13px; cursor:pointer; color:#999; border-bottom:3px solid transparent; margin-bottom:-2px; font-weight:500; }
        .imodal-tab.active { color:#5e64ff; border-bottom-color:#5e64ff; }
        .imodal-tab-content { display:none; }
        .imodal-tab-content.active { display:block; }
        .imodal-raw-box { background:#ffffff; color:#333; padding:20px; border-radius:8px; font-family:Arial,sans-serif; font-size:13px; max-height:340px; overflow-y:auto; border:1px solid #eee; line-height:1.6; }
        .imodal-notes-box { background:#fffde7; border-left:4px solid #ffc107; padding:12px; border-radius:4px; font-size:13px; color:#555; }
        .section-label { font-size:12px; font-weight:700; color:#888; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:10px; }
        .action-grid { display:flex; flex-wrap:wrap; gap:8px; }
        .action-choice-btn { padding:10px 14px; border-radius:8px; border:1px solid #eee; background:#fff; cursor:pointer; font-size:13px; font-weight:600; color:#333; transition:all 0.15s; }
        .action-choice-btn:hover { background:#f5f5ff; transform:translateY(-1px); }
        .action-choice-btn:disabled { opacity:0.5; cursor:not-allowed; transform:none; }
        .imodal-result { background:#e8f5e9; border-radius:8px; padding:14px; margin-top:14px; }
        .result-link { display:block; color:#2e7d32; font-weight:600; text-decoration:none; margin-top:6px; }
        .result-link:hover { text-decoration:underline; }
        .ai-spinner { width:18px; height:18px; border:3px solid #eee; border-top-color:#5e64ff; border-radius:50%; animation:spin 0.7s linear infinite; flex-shrink:0; }
        @keyframes spin { to { transform:rotate(360deg); } }
        .ai-btn { padding:7px 14px; border-radius:6px; border:none; cursor:pointer; font-size:12px; font-weight:600; transition:all 0.15s; }
        .ai-btn-primary { background:#5e64ff; color:#fff; }
        .ai-btn-ghost { background:#f5f5f5; color:#666; }
        .ai-btn-sm { padding:5px 10px; }
        .ai-summary-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; }
        .ai-sum-card { background:#f8f9ff; border-radius:8px; padding:12px; }
        .ai-sum-label { font-size:11px; color:#999; margin-bottom:4px; }
        .ai-sum-val { font-size:14px; font-weight:700; color:#333; }
        .ai-table-wrap { overflow-x:auto; }
        .ai-table { width:100%; border-collapse:collapse; font-size:13px; }
        .ai-table th { background:#f5f5f5; padding:8px 10px; text-align:left; font-weight:600; color:#666; font-size:12px; }
        .ai-table td { padding:8px 10px; border-bottom:1px solid #f0f0f0; }
        .pagination-bar {
    display:flex;
    justify-content:center;
    align-items:center;
    gap:12px;
    margin-top:20px;
}

.page-btn {
    padding:8px 14px;
    border:none;
    background:#5e64ff;
    color:white;
    border-radius:6px;
    cursor:pointer;
    font-size:13px;
}

.page-btn:disabled {
    opacity:0.4;
    cursor:not-allowed;
}

.page-info {
    font-size:13px;
    color:#666;
}
        @media(max-width:600px) { .inbox-row { flex-direction:column; align-items:flex-start; } .inbox-row-right { flex-wrap:wrap; } .ai-summary-grid { grid-template-columns:repeat(2,1fr); } .inbox-search { width:100%; margin-left:0; } }
    `).appendTo('head');
}
