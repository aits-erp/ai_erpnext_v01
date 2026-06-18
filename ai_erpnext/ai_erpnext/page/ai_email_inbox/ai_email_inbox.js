frappe.pages['ai_email_inbox'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: '📧 AI Email Inbox',
        single_column: true
    });

    page.add_button('🔄 Sync Gmail', function() { sync_gmail_and_load_inbox(false); });
    page.add_button('📥 Full Sync History', function() { sync_gmail_and_load_inbox(true); });
    page.add_button('⚙️ Email Settings', function() {
        frappe.set_route('List', 'Email Account');
    });

    inject_inbox_styles();
    render_inbox(wrapper);
    load_inbox();
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
                <div class="stat-card" id="stat-documents">
                    <div class="stat-num">0</div>
                    <div class="stat-label">Documents</div>
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

            <!-- Filter Bar Row 1: Status filters + action buttons -->
            <div class="inbox-filters">
                <button class="filter-btn active" data-status="Pending">🕐 Pending</button>
                <button class="filter-btn" data-status="Documents">📄 Documents</button>
                <button class="filter-btn" data-status="Processed">✅ Processed</button>
                <button class="filter-btn" data-status="Ignored">🗑️ Ignored</button>
                <button class="filter-btn" data-status="All">📋 All</button>

                <div class="filter-actions-right">
                    <button class="delete-all-btn" id="delete-all-btn">🗑 Delete All</button>
                    <button class="delete-selected-btn" id="delete-selected-btn" style="display:none">🗑 Delete Selected</button>
                    <button class="select-mode-btn" id="select-mode-btn">☑ Select</button>
                </div>
            </div>

            <!-- Filter Bar Row 2: Search -->
            <div class="inbox-search-row">
                <div class="search-wrap">
                    <span class="search-icon">🔍</span>
                    <input type="text" id="inbox-search"
                        placeholder="Search by subject or sender..."
                        class="inbox-search">
                </div>
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

                    <div class="imodal-tabs">
                        <button class="imodal-tab active" data-tab="extracted">📊 Extracted Data</button>
                        <button class="imodal-tab" data-tab="raw">📧 Original Email</button>
                    </div>

                    <div class="imodal-tab-content active" id="imodal-extracted">
                        <div class="ai-summary-grid" id="imodal-summary"></div>
                        <div class="section-label" style="margin-top:14px">Line Items</div>
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
                        <div id="imodal-notes-wrap" style="display:none">
                            <div class="section-label" style="margin-top:14px">Notes / Terms</div>
                            <div id="imodal-notes" class="imodal-notes-box"></div>
                        </div>
                    </div>

                    <div class="imodal-tab-content" id="imodal-raw">
                        <div class="imodal-raw-box" id="imodal-raw-content">Loading...</div>
                    </div>

                    <div class="section-label" style="margin-top:18px">⚡ Create Document</div>
                    <div class="action-grid" id="imodal-actions"></div>

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
        _current_page = 1;
        load_inbox();
    });

    // Delete All
    $(wrapper).on('click', '#delete-all-btn', function() {
        var status = _current_filter === 'All' ? '' : _current_filter;
        var label  = _current_filter === 'All' ? 'ALL' : _current_filter;
        frappe.confirm(
            `Delete ALL <strong>${label}</strong> emails permanently? This cannot be undone.`,
            function() {
                frappe.call({
                    method: 'ai_erpnext.api.delete_all_email_queue_items',
                    args: { status: status },
                    callback: function(r) {
                        if (r.message && r.message.success) {
                            frappe.show_alert({ message: 'All emails deleted', indicator: 'green' });
                            selected_emails = [];
                            load_inbox();
                        } else {
                            frappe.show_alert({ message: (r.message && r.message.error) || 'Failed', indicator: 'red' });
                        }
                    }
                });
            }
        );
    });

    // Delete Selected
    $(wrapper).on('click', '#delete-selected-btn', function() {
        if (selected_emails.length === 0) {
            frappe.msgprint('Select emails first');
            return;
        }
        frappe.confirm(
            `Delete ${selected_emails.length} selected email(s) permanently?`,
            function() {
                frappe.call({
                    method: 'ai_erpnext.api.delete_email_queue_items',
                    args: { names: selected_emails },
                    callback: function(r) {
                        if (r.message && r.message.success) {
                            frappe.show_alert({ message: 'Emails deleted', indicator: 'green' });
                            selected_emails = [];
                            selection_mode = false;
                            update_selection_ui();
                            load_inbox();
                        }
                    }
                });
            }
        );
    });

    // Toggle selection mode
    $(wrapper).on('click', '#select-mode-btn', function() {
        selection_mode = !selection_mode;
        if (!selection_mode) selected_emails = [];
        update_selection_ui();
        load_inbox();
    });

    // Search — live with debounce, using wrapper delegation so it always works
    $(wrapper).on('input', '#inbox-search', function() {
        clearTimeout(_search_timer);
        _search_timer = setTimeout(function() {
            _current_page = 1;
            load_inbox();
        }, 400);
    });

    // Individual email checkbox
    $(wrapper).on('change', '.email-checkbox', function() {
        var name = $(this).data('name');
        if ($(this).is(':checked')) {
            if (!selected_emails.includes(name)) selected_emails.push(name);
        } else {
            selected_emails = selected_emails.filter(x => x !== name);
        }
        sync_select_all_checkbox();
        // Show/hide delete selected based on count
        if (selected_emails.length > 0) {
            $('#delete-selected-btn').show();
        } else {
            $('#delete-selected-btn').hide();
        }
    });

    // Select-all checkbox
    $(wrapper).on('change', '#select-all-checkbox', function() {
        var checked = $(this).is(':checked');
        $('.email-checkbox').each(function() {
            var name = $(this).data('name');
            $(this).prop('checked', checked);
            if (checked) {
                if (!selected_emails.includes(name)) selected_emails.push(name);
            } else {
                selected_emails = selected_emails.filter(x => x !== name);
            }
        });
        update_selected_count();
        if (selected_emails.length > 0) {
            $('#delete-selected-btn').show();
        } else {
            $('#delete-selected-btn').hide();
        }
    });

    // Modal tabs
    $(wrapper).on('click', '.imodal-tab', function() {
        var tab = $(this).data('tab');
        $('.imodal-tab').removeClass('active');
        $('.imodal-tab-content').removeClass('active');
        $(this).addClass('active');
        $(`#imodal-${tab}`).addClass('active');
    });
}

var _current_page   = 1;
var _page_length    = 20;
var _current_filter = 'Pending';
var _current_item   = null;
var _current_queue_name = null;
var selected_emails = [];
var selection_mode  = false;
var _current_page_names = [];
var _search_timer   = null;
var _sync_in_progress = false;

function sync_gmail_and_load_inbox(full_sync) {
    if (_sync_in_progress) return;

    _sync_in_progress = true;
    frappe.show_alert({
        message: full_sync ? 'Starting full Gmail sync in background...' : 'Checking Gmail for new emails...',
        indicator: 'blue'
    }, 8);

    frappe.call({
        method: 'ai_erpnext.api.sync_ai_emails_background',
        args: { full_sync: full_sync ? 1 : 0 },
        callback: function(r) {
            var result = r.message || {};
            if (!result.success) {
                frappe.msgprint(result.error || 'Email sync failed. Check Error Log for details.');
                return;
            }

            frappe.show_alert({
                message: full_sync
                    ? 'Full Gmail sync is running. Use this only for first setup/history import.'
                    : 'New-email sync is running. Inbox will refresh automatically.',
                indicator: 'green'
            }, 8);
            load_inbox();
        },
        always: function() {
            _sync_in_progress = false;
        }
    });
}

function update_selection_ui() {
    var btn = $('#select-mode-btn');
    if (selection_mode) {
        btn.text('✕ Cancel').css({ background: '#fee2e2', color: '#dc2626', borderColor: '#fca5a5' });
    } else {
        btn.text('☑ Select').css({ background: '#fff', color: '#666', borderColor: '#e0e0e0' });
        $('#delete-selected-btn').hide();
        selected_emails = [];
        update_selected_count();
    }
}

function sync_select_all_checkbox() {
    if (!selection_mode || _current_page_names.length === 0) return;
    var all_checked = _current_page_names.every(n => selected_emails.includes(n));
    $('#select-all-checkbox').prop('checked', all_checked);
    update_selected_count();
}

function update_selected_count() {
    var count = selected_emails.length;
    $('#selected-count').text(count > 0 ? count + ' selected' : '');
}

function load_inbox() {
    $('#inbox-loading').show();
    $('#inbox-list').hide();
    $('#inbox-empty').hide();

    var search  = $('#inbox-search').val() || '';
    var business_only = _current_filter === 'Documents';
    var status  = (_current_filter === 'All' || business_only) ? '' : _current_filter;

    frappe.call({
        method: 'ai_erpnext.api.get_email_queue',
        args: {
            status:      status,
            search:      search,
            page:        _current_page,
            page_length: _page_length,
            sort_by:     'newest',
            business_only: business_only ? 1 : 0
        },
        callback: function(r) {
            $('#inbox-loading').hide();
            if (!r.message || !r.message.success) return;

            var items  = r.message.items  || [];
            var counts = r.message.counts || {};

            $('#stat-pending .stat-num').text(counts.pending || 0);
            $('#stat-documents .stat-num').text(counts.documents || 0);
            $('#stat-processed .stat-num').text(counts.processed_today || 0);
            $('#stat-ignored .stat-num').text(counts.ignored || 0);

            render_pagination(r.message.pagination);

            if (items.length === 0) {
                _current_page_names = [];
                $('#inbox-empty').show();
                return;
            }

            _current_page_names = items.map(i => i.name);

            // Select-all bar (only in selection mode)
            var select_all_bar = '';
            if (selection_mode) {
                var all_checked = _current_page_names.every(n => selected_emails.includes(n));
                select_all_bar = `
                    <div class="select-all-bar">
                        <label class="select-all-label">
                            <input type="checkbox" id="select-all-checkbox"
                                ${all_checked ? 'checked' : ''}
                                style="width:16px;height:16px;cursor:pointer;accent-color:#5e64ff;">
                            <span>Select all on this page (${items.length})</span>
                        </label>
                        <span id="selected-count" class="selected-count">
                            ${selected_emails.length > 0 ? selected_emails.length + ' selected' : ''}
                        </span>
                    </div>`;
            }

            var html = items.map(function(item) {
                var status_class = {
                    'Pending':   'status-pending',
                    'Processed': 'status-processed',
                    'Ignored':   'status-ignored'
                }[item.status] || '';

                var status_icon = {
                    'Pending':   '🕐',
                    'Processed': '✅',
                    'Ignored':   '🗑️'
                }[item.status] || '';

                var is_checked = selected_emails.includes(item.name);

                return `
                <div class="inbox-row" data-queue="${item.name}">
                    ${selection_mode ? `
                        <input type="checkbox"
                            class="email-checkbox"
                            data-name="${item.name}"
                            ${is_checked ? 'checked' : ''}
                            style="width:16px;height:16px;cursor:pointer;accent-color:#5e64ff;flex-shrink:0;">
                    ` : ''}
                    <div class="inbox-row-left">
                        <div class="inbox-row-subject">${item.email_subject || '(No subject)'}</div>
                        <div class="inbox-row-meta">
                            📤 ${item.from_email || '—'} &nbsp;·&nbsp;
                            🕐 ${frappe.datetime.str_to_user(item.received_on)}
                            ${item.created_document ? `&nbsp;·&nbsp; 📄 ${item.created_document}` : ''}
                        </div>
                    </div>
                    <div class="inbox-row-right">
                        <span class="dtype-chip">${item.suggested_doctype || '?'}</span>
                        <span class="status-chip ${status_class}">${status_icon} ${item.status}</span>
                        ${item.status === 'Pending' ? `
                            <button class="ai-btn ai-btn-primary ai-btn-sm" onclick="open_inbox_modal('${item.name}')">Review →</button>
                            <button class="ai-btn ai-btn-ghost ai-btn-sm" onclick="quick_ignore('${item.name}')">Ignore</button>
                        ` : item.status === 'Ignored' ? `
                            <button class="ai-btn ai-btn-primary ai-btn-sm" onclick="restore_item('${item.name}')">Restore</button>
                            <button class="ai-btn ai-btn-ghost ai-btn-sm" onclick="open_inbox_modal('${item.name}')">View</button>
                        ` : `
                            <button class="ai-btn ai-btn-ghost ai-btn-sm" onclick="open_inbox_modal('${item.name}')">View</button>
                        `}
                    </div>
                </div>`;
            }).join('');

            $('#inbox-list').html(select_all_bar + html).show();
        }
    });
}

function render_pagination(pagination) {
    var page        = (pagination && pagination.page)        || 1;
    var total_pages = (pagination && pagination.total_pages) || 1;

    var html = `
        <button class="page-btn" ${page <= 1 ? 'disabled' : ''} onclick="change_page(${page - 1})">← Prev</button>
        <span class="page-info">Page ${page} of ${total_pages}</span>
        <button class="page-btn" ${page >= total_pages ? 'disabled' : ''} onclick="change_page(${page + 1})">Next →</button>
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
            _current_item       = d;
            _current_queue_name = queue_name;

            $('#imodal-subject').text(d.email_subject || '(No subject)');
            $('#imodal-meta').text('From: ' + d.from_email + '  ·  ' + d.received_on);
            $('#imodal-loading').hide();
            $('#imodal-result').hide();
            $('#imodal-notes-wrap').hide();

            // Reset tabs
            $('.imodal-tab').removeClass('active');
            $('.imodal-tab-content').removeClass('active');
            $('.imodal-tab[data-tab="extracted"]').addClass('active');
            $('#imodal-extracted').addClass('active');

            var ext   = d.extracted || {};
            var party = ext.customer_name || ext.supplier_name || '—';

            $('#imodal-summary').html(`
                <div class="ai-sum-card">
                    <div class="ai-sum-label">Type</div>
                    <select class="review-input" id="review-document-type">
                        ${review_option('Sales Order', ext.document_type)}
                        ${review_option('Sales Invoice', ext.document_type)}
                        ${review_option('Quotation', ext.document_type)}
                        ${review_option('Purchase Order', ext.document_type)}
                        ${review_option('Purchase Invoice', ext.document_type)}
                    </select>
                </div>
                <div class="ai-sum-card">
                    <div class="ai-sum-label">Customer / Supplier</div>
                    <input class="review-input" id="review-party" value="${escape_attr(party === '—' ? '' : party)}" placeholder="Enter customer or supplier">
                </div>
                <div class="ai-sum-card">
                    <div class="ai-sum-label">Date</div>
                    <input class="review-input" id="review-document-date" value="${escape_attr(ext.document_date || '')}" placeholder="YYYY-MM-DD">
                </div>
                <div class="ai-sum-card">
                    <div class="ai-sum-label">Total</div>
                    <div class="ai-sum-val">${ext.currency || 'INR'} <span id="review-grand-total">${ext.grand_total || 0}</span></div>
                </div>
            `);

            var rows = (ext.items || []).map(function(i, idx) {
                return `<tr>
                    <td><input class="review-input review-item-name" data-idx="${idx}" value="${escape_attr(i.item_name || '')}" placeholder="Item name"></td>
                    <td><input class="review-input review-item-qty" data-idx="${idx}" type="number" step="any" value="${escape_attr(i.qty || 1)}"></td>
                    <td><input class="review-input review-item-rate" data-idx="${idx}" type="number" step="any" value="${escape_attr(i.rate || 0)}"></td>
                    <td><input class="review-input review-item-amount" data-idx="${idx}" type="number" step="any" value="${escape_attr(i.amount || 0)}"></td>
                    <td><input class="review-input review-item-uom" data-idx="${idx}" value="${escape_attr(i.uom || 'Nos')}"></td>
                </tr>`;
            }).join('');
            $('#imodal-items').html(rows || '<tr><td colspan="5" style="text-align:center;color:#aaa">No items. Re-extract or add items in the source file.</td></tr>');
            bind_review_calculation();

            if (ext.notes) {
                $('#imodal-notes').text(ext.notes);
                $('#imodal-notes-wrap').show();
            }

            var attachment_html = (d.attachments || []).map(function(att) {
                var file_name = $('<div>').text(att.file_name || 'Attachment').html();
                return `<a class="imodal-attachment" href="${encodeURI(att.file_url || '#')}" target="_blank" rel="noopener">📎 ${file_name}</a>`;
            }).join('');
            var attachments_section = attachment_html
                ? `<div class="section-label" style="margin-bottom:8px">Attachments</div>
                   <div class="imodal-attachments">${attachment_html}</div>`
                : '<div class="imodal-no-attachments">No attachments found on this email.</div>';
            var body_html = d.email_body || '<em style="color:#aaa">(Email body not stored)</em>';
            $('#imodal-raw-content').html(
                attachments_section + '<div class="imodal-email-body">' + body_html + '</div>'
            );

            var doc_type = (ext.document_type || '').toLowerCase();
            var actions  = [];

            if (doc_type.includes('purchase invoice')) {
                actions = [{a:'pi_only', l:'🧾 Purchase Invoice Only', c:'#4CAF50'}];
            } else if (doc_type.includes('purchase order')) {
                actions = [
                    {a:'po_only',  l:'📦 Purchase Order Only',        c:'#2196F3'},
                    {a:'pi_only',  l:'🧾 Purchase Invoice Only',       c:'#4CAF50'},
                    {a:'po_to_pi', l:'📦 → 🧾 PO + Purchase Invoice', c:'#FF9800'}
                ];
            } else if (doc_type.includes('sales invoice')) {
                actions = [{a:'si_only', l:'🧾 Sales Invoice Only', c:'#4CAF50'}];
            } else if (doc_type.includes('sales order')) {
                actions = [
                    {a:'so_only',  l:'📦 Sales Order Only',      c:'#2196F3'},
                    {a:'si_only',  l:'🧾 Sales Invoice Only',     c:'#4CAF50'},
                    {a:'so_to_si', l:'📦 → 🧾 SO + Invoice',     c:'#FF9800'}
                ];
            } else {
                actions = [
                    {a:'quotation_only',  l:'📋 Quotation Only',        c:'#7c6fcd'},
                    {a:'so_only',         l:'📦 Sales Order Only',      c:'#2196F3'},
                    {a:'si_only',         l:'🧾 Sales Invoice Only',    c:'#4CAF50'},
                    {a:'quotation_to_so', l:'📋 → 📦 Quotation + SO',  c:'#FF9800'},
                    {a:'quotation_so_si', l:'📋 → 📦 → 🧾 Full Chain', c:'#F44336'}
                ];
            }

            var warning = '';
            if (doc_type.includes('invoice') && actions.length === 1) {
                warning = `<div style="background:#fff3e0;border-left:4px solid #FF9800;padding:8px 12px;border-radius:4px;font-size:12px;margin-bottom:10px;color:#666">
                    ⚠️ Detected as <strong>${ext.document_type}</strong> — only relevant actions are shown
                </div>`;
            }

            var btns = actions.map(function(x) {
                return `<button class="action-choice-btn" style="border-left:4px solid ${x.c}" onclick="inbox_create('${x.a}','${queue_name}')">${x.l}</button>`;
            }).join('');

            if (d.status === 'Processed') {
                $('#imodal-actions').html(`<div style="color:#888;font-size:13px">Already processed: ${d.created_document || ''}</div>`);
            } else if (d.status === 'Ignored') {
                $('#imodal-actions').html(`
                    <div style="width:100%;margin-bottom:10px;color:#777;font-size:13px">
                        This email is ignored. Restore it to Pending before creating a document.
                    </div>
                    <button class="action-choice-btn" style="border-left:4px solid #5e64ff" onclick="restore_item('${queue_name}')">↩ Restore to Pending</button>
                `);
            } else {
                $('#imodal-actions').html(warning + btns);
            }

            var has_hsn   = (d.extracted.items || []).every(i => i.hsn_code);
            var has_items = (d.extracted.items || []).length > 0;

            if (!has_items || !has_hsn) {
                $('#imodal-actions').prepend(`
                    <div style="width:100%;margin-bottom:12px;padding:10px;background:#fff8e1;border-radius:6px;border-left:4px solid #ffc107;">
                        <div style="font-size:12px;color:#666;margin-bottom:8px;">
                            ⚠️ ${!has_items ? 'No items extracted.' : 'HSN codes missing.'} Re-extract with updated AI prompt:
                        </div>
                        <button class="ai-btn ai-btn-primary ai-btn-sm" id="reextract-btn" onclick="reextract_item('${queue_name}')">🔄 Re-extract with AI</button>
                    </div>
                `);
            }

            $('#inbox-modal-overlay').show();
        }
    });
}

function inbox_create(action, queue_name) {
    if (!_current_item) return;
    var reviewed = collect_review_data();
    if (!reviewed) return;

    $('#imodal-actions').find('button').prop('disabled', true);
    $('#imodal-loading').show();

    frappe.call({
        method: 'ai_erpnext.api.create_from_extracted',
        args: {
            extracted_data_json: JSON.stringify(reviewed),
            action: action
        },
        callback: function(r) {
            $('#imodal-loading').hide();
            if (r.message && r.message.success) {
                var links = (r.message.created || []).map(function(d) {
                    var url = '/app/' + d.doctype.toLowerCase().replace(/ /g, '-') + '/' + encodeURIComponent(d.name);
                    return `<a href="${url}" target="_blank" class="result-link">${d.doctype}: ${d.name} →</a>`;
                }).join('');
                $('#imodal-result-links').html(links);
                $('#imodal-result').show();
                frappe.call({
                    method: 'ai_erpnext.api.mark_queue_processed',
                    args: { queue_name: _current_queue_name, created_document: r.message.created[0].name }
                });
                setTimeout(function() { close_inbox_modal(); load_inbox(); }, 2500);
            } else {
                frappe.show_alert({ message: (r.message && r.message.error) || 'Failed', indicator: 'red' });
                $('#imodal-actions').find('button').prop('disabled', false);
            }
        }
    });
}

function escape_attr(value) {
    return $('<div>').text(value == null ? '' : String(value)).html();
}

function review_option(value, selected) {
    return `<option value="${value}" ${value === selected ? 'selected' : ''}>${value}</option>`;
}

function bind_review_calculation() {
    $('.review-item-qty, .review-item-rate, .review-item-amount').off('input').on('input', function() {
        var row = $(this).closest('tr');
        var qty = flt(row.find('.review-item-qty').val());
        var rate = flt(row.find('.review-item-rate').val());
        if ($(this).hasClass('review-item-qty') || $(this).hasClass('review-item-rate')) {
            row.find('.review-item-amount').val((qty * rate).toFixed(2));
        }
        update_review_total();
    });
    update_review_total();
}

function update_review_total() {
    var total = 0;
    $('.review-item-amount').each(function() {
        total += flt($(this).val());
    });
    $('#review-grand-total').text(total.toFixed(2));
}

function collect_review_data() {
    var ext = $.extend(true, {}, (_current_item && _current_item.extracted) || {});
    var doc_type = $('#review-document-type').val() || ext.document_type || 'Sales Order';
    var party = ($('#review-party').val() || '').trim();

    if (!party) {
        frappe.msgprint('Please enter Customer / Supplier before creating the document.');
        return null;
    }

    ext.document_type = doc_type;
    ext.document_date = ($('#review-document-date').val() || '').trim();

    if (doc_type.toLowerCase().includes('purchase')) {
        ext.supplier_name = party;
        ext.supplier = party;
        ext.customer_name = '';
        ext.customer = '';
    } else {
        ext.customer_name = party;
        ext.customer = party;
        ext.supplier_name = '';
        ext.supplier = '';
    }

    ext.items = [];
    $('#imodal-items tr').each(function() {
        var idx = $(this).find('.review-item-name').data('idx');
        var original_item = ((_current_item.extracted || {}).items || [])[idx] || {};
        var item_name = ($(this).find('.review-item-name').val() || '').trim();
        if (!item_name) return;
        var qty = flt($(this).find('.review-item-qty').val()) || 1;
        var rate = flt($(this).find('.review-item-rate').val());
        var amount = flt($(this).find('.review-item-amount').val()) || (qty * rate);
        ext.items.push({
            item_code: original_item.item_code || '',
            item_name: item_name,
            description: original_item.description || item_name,
            qty: qty,
            rate: rate,
            amount: amount,
            uom: ($(this).find('.review-item-uom').val() || 'Nos').trim(),
            hsn_code: original_item.hsn_code || '',
            tax_rate: original_item.tax_rate || 0
        });
    });

    if (!ext.items.length) {
        frappe.msgprint('Please add at least one item before creating the document.');
        return null;
    }

    ext.grand_total = ext.items.reduce((sum, item) => sum + flt(item.amount), 0);
    ext.total_before_tax = ext.grand_total;
    _current_item.extracted = ext;
    return ext;
}

function close_inbox_modal() {
    $('#inbox-modal-overlay').hide();
    _current_item       = null;
    _current_queue_name = null;
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

function restore_item(queue_name) {
    frappe.call({
        method: 'ai_erpnext.api.restore_queue_item',
        args: { queue_name: queue_name },
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.show_alert({ message: 'Restored to Pending', indicator: 'green' });
                close_inbox_modal();
                _current_filter = 'Pending';
                $('.filter-btn').removeClass('active');
                $('.filter-btn[data-status="Pending"]').addClass('active');
                _current_page = 1;
                load_inbox();
            } else {
                frappe.show_alert({ message: 'Restore failed', indicator: 'red' });
            }
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
                frappe.show_alert({ message: 'Re-extracted successfully', indicator: 'green' });
                close_inbox_modal();
                setTimeout(function() { open_inbox_modal(queue_name); }, 300);
            } else {
                frappe.show_alert({ message: (r.message && r.message.error) || 'Failed', indicator: 'red' });
                $('#reextract-btn').prop('disabled', false).text('🔄 Re-extract with AI');
            }
        }
    });
}

function inject_inbox_styles() {
    $('<style>').text(`

        .inbox-root { max-width: 960px; margin: 0 auto; padding: 20px; }

        /* Stats */
        .inbox-stats { display: grid; grid-template-columns: repeat(5,minmax(0,1fr)); gap: 12px; margin-bottom: 20px; }
        .stat-card { background: #fff; border: 1px solid #eee; border-radius: 10px; padding: 16px; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,0.04); transition: transform 0.15s, box-shadow 0.15s; }
        .stat-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
        .stat-num   { font-size: 28px; font-weight: 800; color: #5e64ff; }
        .stat-label { font-size: 12px; color: #aaa; margin-top: 4px; }

        /* Filter Row 1 */
        .inbox-filters {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 10px;
            flex-wrap: wrap;
        }
        .filter-btn {
            padding: 7px 16px;
            border-radius: 20px;
            border: 1px solid #e0e0e0;
            background: #fff;
            cursor: pointer;
            font-size: 13px;
            color: #666;
            font-weight: 500;
            transition: all 0.15s;
        }
        .filter-btn:hover  { background: #f5f5f5; }
        .filter-btn.active { background: #5e64ff; color: #fff; border-color: #5e64ff; box-shadow: 0 2px 8px rgba(94,100,255,0.25); }

        /* Right-side action buttons pushed to end */
        .filter-actions-right {
            margin-left: auto;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .delete-all-btn {
            background: #fff0f0;
            color: #c0392b;
            border: 1px solid #f5c6c6;
            padding: 7px 14px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            transition: all 0.15s;
            white-space: nowrap;
        }
        .delete-all-btn:hover { background: #ffe0e0; border-color: #e57373; }

        .delete-selected-btn {
            background: #fff;
            color: #c0392b;
            border: 1px solid #f5c6c6;
            padding: 7px 14px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            transition: all 0.15s;
            white-space: nowrap;
        }
        .delete-selected-btn:hover { background: #fff0f0; border-color: #e57373; }

        .select-mode-btn {
            background: #fff;
            color: #666;
            border: 1px solid #e0e0e0;
            padding: 7px 14px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            transition: all 0.15s;
            white-space: nowrap;
        }
        .select-mode-btn:hover { background: #f5f5f5; }

        /* Filter Row 2: Search */
        .inbox-search-row {
            display: flex;
            align-items: center;
            margin-bottom: 16px;
        }
        .search-wrap {
            position: relative;
            display: flex;
            align-items: center;
            width: 50%;
        }
        .search-icon {
            position: absolute;
            left: 12px;
            font-size: 13px;
            pointer-events: none;
            line-height: 1;
        }
        .inbox-search {
            width: 100%;
            padding: 8px 14px 8px 34px;
            border-radius: 20px;
            border: 1px solid #e0e0e0;
            font-size: 13px;
            outline: none;
            background: #fff;
            transition: border-color 0.15s, box-shadow 0.15s;
            box-sizing: border-box;
        }
        .inbox-search:focus {
            border-color: #5e64ff;
            box-shadow: 0 0 0 3px rgba(94,100,255,0.1);
        }

        .imodal-attachments { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:14px; }
        .imodal-attachment { display:inline-block; padding:7px 10px; border:1px solid #d9dcff; border-radius:6px; background:#f5f6ff; font-size:12px; }
        .imodal-no-attachments { color:#999; font-size:12px; margin-bottom:14px; }
        .imodal-email-body { border-top:1px solid #eee; padding-top:14px; }

        /* Select-all bar */
        .select-all-bar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #f0f1ff;
            border: 1px solid #d0d3ff;
            border-radius: 8px;
            padding: 10px 16px;
            margin-bottom: 8px;
        }
        .select-all-label {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 13px;
            font-weight: 600;
            color: #5e64ff;
            cursor: pointer;
            user-select: none;
        }
        .selected-count {
            font-size: 12px;
            font-weight: 700;
            color: #5e64ff;
            background: #e8eaff;
            padding: 3px 10px;
            border-radius: 12px;
        }

        /* Email rows */
        .inbox-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #fff;
            border: 1px solid #eee;
            border-radius: 8px;
            padding: 14px 16px;
            margin-bottom: 8px;
            transition: box-shadow 0.15s, border-color 0.15s;
            gap: 12px;
        }
        .inbox-row:hover { box-shadow: 0 2px 10px rgba(0,0,0,0.07); border-color: #ddd; }
        .inbox-row-left  { flex: 1; min-width: 0; }
        .inbox-row-subject { font-weight: 600; color: #333; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .inbox-row-meta    { font-size: 12px; color: #aaa; margin-top: 4px; }
        .inbox-row-right   { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }

        /* Chips */
        .dtype-chip { background: #e8eaff; color: #5e64ff; border-radius: 12px; padding: 3px 10px; font-size: 12px; font-weight: 600; }
        .status-chip { border-radius: 12px; padding: 3px 10px; font-size: 12px; font-weight: 600; }
        .status-pending   { background: #fff8e1; color: #f57f17; }
        .status-processed { background: #e8f5e9; color: #2e7d32; }
        .status-ignored   { background: #f5f5f5; color: #999; }

        /* Loading / Empty */
        .inbox-loading { display: flex; align-items: center; gap: 10px; color: #888; padding: 30px 0; justify-content: center; }
        .inbox-empty   { text-align: center; padding: 60px; color: #bbb; }
        .inbox-empty-sub { font-size: 12px; margin-top: 6px; }

        /* Buttons */
        .ai-btn { padding: 7px 14px; border-radius: 6px; border: none; cursor: pointer; font-size: 12px; font-weight: 600; transition: all 0.15s; }
        .ai-btn-primary { background: #5e64ff; color: #fff; }
        .ai-btn-primary:hover { background: #4a50e0; }
        .ai-btn-ghost { background: #f5f5f5; color: #666; }
        .ai-btn-ghost:hover { background: #eaeaea; }
        .ai-btn-sm { padding: 5px 10px; }

        /* Pagination */
        .pagination-bar { display: flex; justify-content: center; align-items: center; gap: 12px; margin-top: 20px; }
        .page-btn  { padding: 8px 14px; border: none; background: #5e64ff; color: white; border-radius: 6px; cursor: pointer; font-size: 13px; transition: background 0.15s; }
        .page-btn:hover:not(:disabled) { background: #4a50e0; }
        .page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
        .page-info { font-size: 13px; color: #666; }

        /* Modal */
        .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.55); z-index: 9999; display: flex; align-items: center; justify-content: center; padding: 20px; }
        .inbox-modal   { background: #fff; border-radius: 14px; width: 100%; max-width: 700px; max-height: 90vh; overflow-y: auto; box-shadow: 0 24px 80px rgba(0,0,0,0.25); }
        .inbox-modal-header { display: flex; justify-content: space-between; align-items: flex-start; padding: 18px 20px; border-bottom: 1px solid #eee; position: sticky; top: 0; background: #fff; z-index: 1; border-radius: 14px 14px 0 0; }
        .imodal-subject { font-weight: 700; font-size: 15px; color: #1a1a2e; }
        .imodal-meta    { font-size: 12px; color: #aaa; margin-top: 4px; }
        .modal-close    { background: #f5f5f5; border: none; width: 28px; height: 28px; border-radius: 50%; font-size: 16px; cursor: pointer; color: #888; display: flex; align-items: center; justify-content: center; transition: background 0.15s; }
        .modal-close:hover { background: #fee2e2; color: #dc2626; }
        .inbox-modal-body { padding: 20px; }

        /* Modal Tabs */
        .imodal-tabs { display: flex; gap: 4px; margin-bottom: 16px; border-bottom: 2px solid #f0f0f0; }
        .imodal-tab  { background: none; border: none; padding: 8px 16px; font-size: 13px; cursor: pointer; color: #999; border-bottom: 3px solid transparent; margin-bottom: -2px; font-weight: 500; transition: color 0.15s; }
        .imodal-tab:hover  { color: #5e64ff; }
        .imodal-tab.active { color: #5e64ff; border-bottom-color: #5e64ff; }
        .imodal-tab-content        { display: none; }
        .imodal-tab-content.active { display: block; }

        /* Raw box */
        .imodal-raw-box { background: #fafafa; color: #333; padding: 20px; border-radius: 8px; font-family: Arial, sans-serif; font-size: 13px; max-height: 340px; overflow-y: auto; border: 1px solid #eee; line-height: 1.6; }

        /* Notes */
        .imodal-notes-box { background: #fffde7; border-left: 4px solid #ffc107; padding: 12px; border-radius: 4px; font-size: 13px; color: #555; }

        /* Section label */
        .section-label { font-size: 12px; font-weight: 700; color: #888; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px; }

        /* Actions */
        .action-grid { display: flex; flex-wrap: wrap; gap: 8px; }
        .action-choice-btn { padding: 10px 14px; border-radius: 8px; border: 1px solid #eee; background: #fff; cursor: pointer; font-size: 13px; font-weight: 600; color: #333; transition: all 0.15s; }
        .action-choice-btn:hover    { background: #f5f5ff; transform: translateY(-1px); box-shadow: 0 3px 8px rgba(0,0,0,0.07); }
        .action-choice-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

        /* Result */
        .imodal-result { background: #e8f5e9; border-radius: 8px; padding: 14px; margin-top: 14px; }
        .result-link { display: block; color: #2e7d32; font-weight: 600; text-decoration: none; margin-top: 6px; }
        .result-link:hover { text-decoration: underline; }

        /* Summary */
        .ai-summary-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 10px; }
        .ai-sum-card  { background: #f8f9ff; border-radius: 8px; padding: 12px; }
        .ai-sum-label { font-size: 11px; color: #999; margin-bottom: 4px; }
        .ai-sum-val   { font-size: 14px; font-weight: 700; color: #333; }

        /* Table */
        .ai-table-wrap { overflow-x: auto; border: 1px solid #f0f0f0; border-radius: 8px; margin-top: 8px; }
        .ai-table    { width: 100%; border-collapse: collapse; font-size: 13px; }
        .ai-table th { background: #f8f8f8; padding: 8px 10px; text-align: left; font-weight: 700; color: #666; font-size: 12px; }
        .ai-table td { padding: 8px 10px; border-bottom: 1px solid #f5f5f5; }
        .ai-table tr:last-child td { border-bottom: none; }

        .review-input {
            width: 100%;
            min-width: 86px;
            padding: 7px 8px;
            border: 1px solid #dfe3ea;
            border-radius: 6px;
            background: #fff;
            font-size: 12px;
            color: #333;
            outline: none;
            box-sizing: border-box;
        }
        .review-input:focus {
            border-color: #5e64ff;
            box-shadow: 0 0 0 2px rgba(94,100,255,0.12);
        }
        .review-item-name { min-width: 180px; }
        .review-item-qty,
        .review-item-rate,
        .review-item-amount { min-width: 90px; }
        .review-item-uom { min-width: 70px; }

        /* Spinner */
        .ai-spinner { width: 18px; height: 18px; border: 3px solid #eee; border-top-color: #5e64ff; border-radius: 50%; animation: spin 0.7s linear infinite; flex-shrink: 0; }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* Responsive */
        @media (max-width: 600px) {
            .inbox-stats { grid-template-columns: repeat(2,minmax(0,1fr)); }
            .inbox-filters { flex-wrap: wrap; }
            .filter-actions-right { margin-left: 0; width: 100%; justify-content: flex-start; }
            .inbox-row { flex-direction: column; align-items: flex-start; }
            .inbox-row-right { flex-wrap: wrap; }
            .ai-summary-grid { grid-template-columns: repeat(2,1fr); }
        }
    `).appendTo('head');
}
