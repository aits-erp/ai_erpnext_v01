frappe.pages['ai_document_processor'].on_page_load = function(wrapper) {

    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: '🤖 AI Document Processor',
        single_column: true
    });

    // ── Add page buttons ──
    page.add_button('📧 Refresh Emails', function() { load_email_queue(); });
    page.add_button('📄 Upload Document', function() { show_tab('upload'); });

    inject_styles();
    render_page(wrapper);
    init_logic(wrapper);
    load_email_queue();

    // Auto-refresh email queue every 60 seconds
    setInterval(load_email_queue, 60000);
};

// ─────────────────────────────────────────────────────────
function render_page(wrapper) {
    $(wrapper).find('.layout-main-section').html(`
        <div class="ai-root">

            <!-- TABS -->
            <div class="ai-tabs">
                <button class="ai-tab active" data-tab="upload">📄 Upload Document</button>
                <button class="ai-tab" data-tab="emails">
                    📧 Email Queue
                    <span class="ai-badge-count" id="email-count-badge" style="display:none">0</span>
                </button>
            </div>

            <!-- ── TAB: UPLOAD ── -->
            <div class="ai-tab-content active" id="tab-upload">
                <div class="ai-card">
                    <div class="ai-drop-zone" id="ai-drop-zone">
                        <div class="ai-drop-icon">📄</div>
                        <div class="ai-drop-title">Drop file here or click to browse</div>
                        <div class="ai-drop-sub">PDF, JPG, PNG — Quotation, Invoice, Order</div>
                        <input type="file" id="ai-file-input" accept=".pdf,.jpg,.jpeg,.png,.webp" style="display:none">
                    </div>
                    <div id="ai-file-info" style="display:none" class="ai-file-info">
                        <span id="ai-file-icon">📎</span>
                        <span id="ai-file-name-text"></span>
                        <span class="ai-file-remove" id="ai-remove-file">✕</span>
                    </div>
                    <button id="ai-extract-btn" class="ai-btn ai-btn-primary" style="display:none">
                        ⚡ Extract with AI
                    </button>
                    <div id="ai-upload-loading" class="ai-loading" style="display:none">
                        <div class="ai-spinner"></div>
                        <span>Claude is reading your document...</span>
                    </div>
                </div>

                <!-- Extraction Result + Action Panel -->
                <div id="ai-action-panel" style="display:none" class="ai-card">
                    <div class="ai-section-title">📋 Extracted Information</div>

                    <!-- Summary Cards -->
                    <div class="ai-summary-grid" id="ai-summary-grid"></div>

                    <!-- Items Table -->
                    <div class="ai-section-title" style="margin-top:16px">🧾 Line Items</div>
                    <div class="ai-table-wrap">
                        <table class="ai-table" id="ai-items-table">
                            <thead>
                                <tr>
                                    <th>Item</th>
                                    <th>Qty</th>
                                    <th>Rate</th>
                                    <th>Amount</th>
                                </tr>
                            </thead>
                            <tbody id="ai-items-body"></tbody>
                        </table>
                    </div>

                    <!-- Action Choices -->
                    <div class="ai-section-title" style="margin-top:20px">⚡ What do you want to create?</div>
                    <div class="ai-action-grid" id="ai-action-grid"></div>

                    <div id="ai-create-loading" class="ai-loading" style="display:none">
                        <div class="ai-spinner"></div>
                        <span>Creating documents in ERPNext...</span>
                    </div>
                </div>

                <!-- Created Docs Result -->
                <div id="ai-created-result" style="display:none" class="ai-card ai-success-card">
                    <div class="ai-section-title" style="color:#2e7d32">✅ Documents Created</div>
                    <div id="ai-created-links"></div>
                    <button class="ai-btn ai-btn-outline" onclick="reset_upload_ui()" style="margin-top:12px">
                        ↺ Process Another Document
                    </button>
                </div>
            </div>

            <!-- ── TAB: EMAIL QUEUE ── -->
            <div class="ai-tab-content" id="tab-emails">
                <div id="email-queue-loading" class="ai-loading">
                    <div class="ai-spinner"></div> Loading email queue...
                </div>
                <div id="email-queue-empty" style="display:none" class="ai-empty-state">
                    <div style="font-size:40px">📭</div>
                    <div>No pending emails with quotations/orders</div>
                    <div style="font-size:12px;color:#aaa;margin-top:6px">
                        Queue updates automatically when new emails arrive
                    </div>
                </div>
                <div id="email-queue-list"></div>
            </div>

        </div>

        <!-- ── REVIEW MODAL ── -->
        <div id="ai-modal-overlay" class="ai-modal-overlay" style="display:none">
            <div class="ai-modal">
                <div class="ai-modal-header">
                    <span id="modal-title">📧 Review Extracted Data</span>
                    <button class="ai-modal-close" onclick="close_modal()">✕</button>
                </div>
                <div class="ai-modal-body">
                    <div id="modal-summary-grid" class="ai-summary-grid"></div>
                    <div class="ai-section-title" style="margin-top:12px">Line Items</div>
                    <div class="ai-table-wrap">
                        <table class="ai-table">
                            <thead><tr><th>Item</th><th>Qty</th><th>Rate</th><th>Amount</th></tr></thead>
                            <tbody id="modal-items-body"></tbody>
                        </table>
                    </div>
                    <div class="ai-section-title" style="margin-top:16px">Create As:</div>
                    <div class="ai-action-grid" id="modal-action-grid"></div>
                </div>
                <div id="modal-loading" class="ai-loading" style="display:none">
                    <div class="ai-spinner"></div> Creating...
                </div>
                <div id="modal-result" style="display:none" class="ai-success-card" style="padding:12px;margin:12px">
                    <strong>✅ Created:</strong>
                    <div id="modal-result-links"></div>
                </div>
            </div>
        </div>
    `);
}

// ─────────────────────────────────────────────────────────
var _extracted_data = null;
var _current_queue_item = null;

function init_logic(wrapper) {

    // Tab switching
    $(wrapper).on('click', '.ai-tab', function() {
        var tab = $(this).data('tab');
        show_tab(tab);
    });

    // Drop zone
    $('#ai-drop-zone').on('click', function() { $('#ai-file-input').click(); });
    $('#ai-file-input').on('change', function(e) {
        if (e.target.files[0]) handle_file(e.target.files[0]);
    });
    $('#ai-drop-zone').on('dragover', function(e) {
        e.preventDefault(); $(this).addClass('dragover');
    }).on('dragleave', function() {
        $(this).removeClass('dragover');
    }).on('drop', function(e) {
        e.preventDefault(); $(this).removeClass('dragover');
        if (e.originalEvent.dataTransfer.files[0])
            handle_file(e.originalEvent.dataTransfer.files[0]);
    });

    $('#ai-remove-file').on('click', function() { reset_upload_ui(); });

    // Extract button
    $('#ai-extract-btn').on('click', function() { do_extract(); });
}

function show_tab(tab) {
    $('.ai-tab').removeClass('active');
    $('.ai-tab-content').removeClass('active');
    $(`.ai-tab[data-tab="${tab}"]`).addClass('active');
    $(`#tab-${tab}`).addClass('active');
    if (tab === 'emails') load_email_queue();
}

// ── FILE UPLOAD ──────────────────────────────────────────
var _uploaded_url = null;

function handle_file(file) {
    var ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf','jpg','jpeg','png','webp'].includes(ext)) {
        frappe.show_alert({message: 'Unsupported file type: ' + ext, indicator: 'red'});
        return;
    }
    $('#ai-file-info').show();
    $('#ai-file-name-text').text(file.name);
    $('#ai-file-icon').text(ext === 'pdf' ? '📄' : '🖼️');
    $('#ai-extract-btn').hide();
    frappe.show_alert({message: 'Uploading...', indicator: 'blue'});

    var fd = new FormData();
    fd.append('file', file);
    fd.append('is_private', 0);
    fd.append('folder', 'Home/Attachments');

    $.ajax({
        url: '/api/method/upload_file',
        type: 'POST', data: fd,
        processData: false, contentType: false,
        headers: {'X-Frappe-CSRF-Token': frappe.csrf_token},
        success: function(r) {
            if (r.message && r.message.file_url) {
                _uploaded_url = r.message.file_url;
                $('#ai-extract-btn').show();
                frappe.show_alert({message: 'File ready. Click Extract.', indicator: 'green'});
            } else {
                frappe.show_alert({message: 'Upload failed', indicator: 'red'});
            }
        },
        error: function() {
            frappe.show_alert({message: 'Upload error', indicator: 'red'});
        }
    });
}

function do_extract() {
    if (!_uploaded_url) return;
    $('#ai-extract-btn').hide();
    $('#ai-upload-loading').show();
    $('#ai-action-panel').hide();
    $('#ai-created-result').hide();

    frappe.call({
        method: 'ai_erpnext.api.process_document',
        args: {file_url: _uploaded_url},
        callback: function(r) {
            $('#ai-upload-loading').hide();
            if (r.message && r.message.success) {
                _extracted_data = r.message.extracted_data;
                render_action_panel(_extracted_data, '#ai-summary-grid', '#ai-items-body', '#ai-action-grid', 'upload');
                $('#ai-action-panel').show();
            } else {
                var err = (r.message && r.message.error) || 'Extraction failed';
                frappe.show_alert({message: err, indicator: 'red'});
                $('#ai-extract-btn').show();
            }
        }
    });
}

// ── RENDER EXTRACTED DATA + ACTION BUTTONS ───────────────
function render_action_panel(data, summaryEl, itemsEl, actionsEl, context) {

    // Summary cards
    var party = data.customer_name || data.supplier_name || '—';
    var total = data.grand_total || data.total_amount || '—';
    var date  = data.document_date || '—';
    var dtype = data.document_type || '—';

    $(summaryEl).html(`
        <div class="ai-sum-card"><div class="ai-sum-label">Document Type</div><div class="ai-sum-val">${dtype}</div></div>
        <div class="ai-sum-card"><div class="ai-sum-label">Party</div><div class="ai-sum-val">${party}</div></div>
        <div class="ai-sum-card"><div class="ai-sum-label">Date</div><div class="ai-sum-val">${date}</div></div>
        <div class="ai-sum-card"><div class="ai-sum-label">Grand Total</div><div class="ai-sum-val">${data.currency || 'INR'} ${total}</div></div>
    `);

    // Items table
    var rows = '';
    (data.items || []).forEach(function(item) {
        rows += `<tr>
            <td>${item.item_name || '—'}</td>
            <td>${item.qty || 1}</td>
            <td>${item.rate || 0}</td>
            <td>${item.amount || 0}</td>
        </tr>`;
    });
    $(itemsEl).html(rows || '<tr><td colspan="4" style="text-align:center;color:#aaa">No items found</td></tr>');

    // Action buttons — depends on doc type
    var isSale = ['Sales Order','Quotation','Sales Invoice'].includes(data.document_type);
    var isBuy  = ['Purchase Order','Purchase Invoice'].includes(data.document_type);

    var actions = [];
    if (isSale || !isBuy) {
        actions = [
            {action: 'quotation_only',   label: '📋 Quotation Only',              color: '#7c6fcd'},
            {action: 'so_only',          label: '📦 Sales Order Only',            color: '#2196F3'},
            {action: 'si_only',          label: '🧾 Sales Invoice Only',          color: '#4CAF50'},
            {action: 'quotation_to_so',  label: '📋→📦 Quotation + Sales Order', color: '#FF9800'},
            {action: 'quotation_so_si',  label: '📋→📦→🧾 Full Chain',           color: '#F44336'},
        ];
    } else {
        actions = [
            {action: 'po_only', label: '📦 Purchase Order Only', color: '#2196F3'},
            {action: 'pi_only', label: '🧾 Purchase Invoice Only', color: '#4CAF50'},
        ];
    }

    var btns = actions.map(function(a) {
        return `<button class="ai-action-btn" 
                    style="border-left: 4px solid ${a.color}"
                    data-action="${a.action}" 
                    data-context="${context}">
                    ${a.label}
                </button>`;
    }).join('');

    $(actionsEl).html(btns);

    // Bind action button clicks
    $(actionsEl).find('.ai-action-btn').off('click').on('click', function() {
        var action  = $(this).data('action');
        var ctx     = $(this).data('context');
        do_create(action, ctx);
    });
}

function do_create(action, context) {
    var data = (context === 'modal') ? _current_queue_item : _extracted_data;
    if (!data) return;

    if (context === 'upload') {
        $('#ai-action-grid').find('.ai-action-btn').prop('disabled', true);
        $('#ai-create-loading').show();
    } else {
        $('#modal-action-grid').find('.ai-action-btn').prop('disabled', true);
        $('#modal-loading').show();
    }

    frappe.call({
        method: 'ai_erpnext.api.create_from_extracted',
        args: {
            extracted_data_json: JSON.stringify(data),
            action: action
        },
        callback: function(r) {
            if (context === 'upload') {
                $('#ai-create-loading').hide();
            } else {
                $('#modal-loading').hide();
            }

            if (r.message && r.message.success) {
                var links = (r.message.created || []).map(function(d) {
                    var url = '/app/' + d.doctype.toLowerCase().replace(/ /g,'-') + '/' + encodeURIComponent(d.name);
                    return `<a href="${url}" target="_blank" class="ai-doc-link">${d.doctype}: ${d.name} →</a>`;
                }).join('');

                if (context === 'upload') {
                    $('#ai-created-links').html(links);
                    $('#ai-created-result').show();
                    $('#ai-action-panel').hide();
                } else {
                    $('#modal-result-links').html(links);
                    $('#modal-result').show();
                    // Mark queue item processed
                    if (_current_queue_item && _current_queue_item._queue_name) {
                        frappe.call({
                            method: 'ai_erpnext.api.ignore_queue_item',
                            args: {queue_name: _current_queue_item._queue_name}
                        });
                        setTimeout(function() { close_modal(); load_email_queue(); }, 2000);
                    }
                }
                frappe.show_alert({message: 'Documents created successfully!', indicator: 'green'});
            } else {
                var err = (r.message && r.message.error) || 'Creation failed';
                frappe.show_alert({message: err, indicator: 'red'});
                if (context === 'upload') {
                    $('#ai-action-grid').find('.ai-action-btn').prop('disabled', false);
                } else {
                    $('#modal-action-grid').find('.ai-action-btn').prop('disabled', false);
                }
            }
        }
    });
}

// ── EMAIL QUEUE ──────────────────────────────────────────
function load_email_queue() {
    $('#email-queue-loading').show();
    $('#email-queue-list').empty();
    $('#email-queue-empty').hide();

    frappe.call({
        method: 'ai_erpnext.api.get_pending_emails',
        callback: function(r) {
            $('#email-queue-loading').hide();
            if (!r.message || !r.message.success) return;

            var items = r.message.items || [];

            // Update badge
            if (items.length > 0) {
                $('#email-count-badge').text(items.length).show();
            } else {
                $('#email-count-badge').hide();
                $('#email-queue-empty').show();
                return;
            }

            var html = items.map(function(item) {
                return `
                <div class="ai-email-card" data-queue="${item.name}">
                    <div class="ai-email-header">
                        <span class="ai-email-subject">${item.email_subject || '(No subject)'}</span>
                        <span class="ai-dtype-badge">${item.suggested_doctype || '?'}</span>
                    </div>
                    <div class="ai-email-meta">
                        From: <strong>${item.from_email}</strong> &nbsp;|&nbsp;
                        ${frappe.datetime.str_to_user(item.received_on)}
                    </div>
                    <div class="ai-email-actions">
                        <button class="ai-btn ai-btn-primary ai-btn-sm" onclick="open_review_modal('${item.name}')">
                            👁️ Review &amp; Create
                        </button>
                        <button class="ai-btn ai-btn-ghost ai-btn-sm" onclick="ignore_email('${item.name}')">
                            🗑️ Ignore
                        </button>
                    </div>
                </div>`;
            }).join('');

            $('#email-queue-list').html(html);
        }
    });
}

function open_review_modal(queue_name) {
    frappe.call({
        method: 'ai_erpnext.api.get_queue_item_detail',
        args: {queue_name: queue_name},
        callback: function(r) {
            if (!r.message || !r.message.success) return;
            var d = r.message.data;
            _current_queue_item = d.extracted;
            _current_queue_item._queue_name = queue_name;

            $('#modal-title').text('📧 ' + d.email_subject);
            $('#modal-result').hide();
            $('#modal-loading').hide();

            render_action_panel(d.extracted, '#modal-summary-grid', '#modal-items-body', '#modal-action-grid', 'modal');
            $('#ai-modal-overlay').show();
        }
    });
}

function close_modal() {
    $('#ai-modal-overlay').hide();
    _current_queue_item = null;
}

function ignore_email(queue_name) {
    frappe.call({
        method: 'ai_erpnext.api.ignore_queue_item',
        args: {queue_name: queue_name},
        callback: function() {
            frappe.show_alert({message: 'Ignored', indicator: 'orange'});
            load_email_queue();
        }
    });
}

function reset_upload_ui() {
    _uploaded_url = null;
    _extracted_data = null;
    $('#ai-file-info').hide();
    $('#ai-extract-btn').hide();
    $('#ai-action-panel').hide();
    $('#ai-created-result').hide();
    $('#ai-upload-loading').hide();
    $('#ai-file-input').val('');
}

// ── STYLES ───────────────────────────────────────────────
function inject_styles() {
    $('<style>').text(`
        .ai-root { max-width: 860px; margin: 0 auto; padding: 20px; }
        .ai-tabs { display:flex; gap:8px; margin-bottom:20px; border-bottom:2px solid #eee; padding-bottom:0; }
        .ai-tab { background:none; border:none; padding:10px 20px; font-size:14px; cursor:pointer; color:#888; border-bottom:3px solid transparent; margin-bottom:-2px; font-weight:500; }
        .ai-tab.active { color:#5e64ff; border-bottom-color:#5e64ff; }
        .ai-tab-content { display:none; }
        .ai-tab-content.active { display:block; }
        .ai-badge-count { background:#e53935; color:#fff; border-radius:10px; padding:1px 6px; font-size:11px; margin-left:6px; }
        .ai-card { background:#fff; border:1px solid #eee; border-radius:10px; padding:20px; margin-bottom:16px; box-shadow:0 1px 4px rgba(0,0,0,0.05); }
        .ai-success-card { background:#f6fff8; border-color:#b2dfdb; }
        .ai-drop-zone { border:2px dashed #d0d5dd; border-radius:8px; padding:40px 20px; text-align:center; cursor:pointer; transition:all 0.2s; }
        .ai-drop-zone:hover, .ai-drop-zone.dragover { border-color:#5e64ff; background:#f5f5ff; }
        .ai-drop-icon { font-size:36px; margin-bottom:10px; }
        .ai-drop-title { font-size:15px; font-weight:600; color:#333; }
        .ai-drop-sub { font-size:12px; color:#aaa; margin-top:4px; }
        .ai-file-info { display:flex; align-items:center; gap:8px; padding:10px 14px; background:#f5f5ff; border-radius:6px; margin-top:12px; }
        .ai-file-remove { margin-left:auto; cursor:pointer; color:#999; font-size:16px; }
        .ai-file-remove:hover { color:#e53935; }
        .ai-btn { padding:8px 18px; border-radius:6px; border:none; cursor:pointer; font-size:13px; font-weight:600; transition:all 0.15s; }
        .ai-btn-primary { background:#5e64ff; color:#fff; margin-top:12px; }
        .ai-btn-primary:hover { background:#4a4fcc; }
        .ai-btn-outline { background:#fff; color:#5e64ff; border:1px solid #5e64ff; }
        .ai-btn-ghost { background:#f5f5f5; color:#666; }
        .ai-btn-sm { padding:5px 12px; font-size:12px; margin-top:0; }
        .ai-loading { display:flex; align-items:center; gap:10px; color:#666; font-size:13px; padding:14px 0; }
        .ai-spinner { width:18px; height:18px; border:3px solid #eee; border-top-color:#5e64ff; border-radius:50%; animation:spin 0.7s linear infinite; flex-shrink:0; }
        @keyframes spin { to { transform:rotate(360deg); } }
        .ai-section-title { font-size:13px; font-weight:700; color:#555; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:10px; }
        .ai-summary-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; }
        .ai-sum-card { background:#f8f9ff; border-radius:8px; padding:12px; }
        .ai-sum-label { font-size:11px; color:#999; margin-bottom:4px; }
        .ai-sum-val { font-size:14px; font-weight:700; color:#333; word-break:break-word; }
        .ai-table-wrap { overflow-x:auto; }
        .ai-table { width:100%; border-collapse:collapse; font-size:13px; }
        .ai-table th { background:#f5f5f5; padding:8px 10px; text-align:left; font-weight:600; color:#666; font-size:12px; }
        .ai-table td { padding:8px 10px; border-bottom:1px solid #f0f0f0; }
        .ai-action-grid { display:flex; flex-wrap:wrap; gap:10px; }
        .ai-action-btn { padding:10px 16px; border-radius:8px; border:1px solid #eee; background:#fff; cursor:pointer; font-size:13px; font-weight:600; color:#333; transition:all 0.15s; text-align:left; }
        .ai-action-btn:hover { background:#f5f5ff; transform:translateY(-1px); box-shadow:0 2px 8px rgba(0,0,0,0.1); }
        .ai-action-btn:disabled { opacity:0.5; cursor:not-allowed; transform:none; }
        .ai-doc-link { display:block; padding:8px 12px; background:#e8f5e9; border-radius:6px; color:#2e7d32; text-decoration:none; font-weight:600; margin-top:6px; }
        .ai-doc-link:hover { background:#c8e6c9; }
        .ai-email-card { background:#fff; border:1px solid #eee; border-radius:8px; padding:14px 16px; margin-bottom:10px; transition:box-shadow 0.15s; }
        .ai-email-card:hover { box-shadow:0 2px 8px rgba(0,0,0,0.08); }
        .ai-email-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; }
        .ai-email-subject { font-weight:600; color:#333; font-size:14px; }
        .ai-dtype-badge { background:#e8eaff; color:#5e64ff; border-radius:12px; padding:2px 10px; font-size:12px; font-weight:600; }
        .ai-email-meta { font-size:12px; color:#999; margin-bottom:10px; }
        .ai-email-actions { display:flex; gap:8px; }
        .ai-empty-state { text-align:center; padding:60px 20px; color:#bbb; }
        .ai-modal-overlay { position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.5); z-index:9999; display:flex; align-items:center; justify-content:center; }
        .ai-modal { background:#fff; border-radius:12px; width:90%; max-width:680px; max-height:85vh; overflow-y:auto; box-shadow:0 20px 60px rgba(0,0,0,0.2); }
        .ai-modal-header { display:flex; justify-content:space-between; align-items:center; padding:16px 20px; border-bottom:1px solid #eee; font-weight:700; font-size:15px; }
        .ai-modal-close { background:none; border:none; font-size:18px; cursor:pointer; color:#999; }
        .ai-modal-body { padding:20px; }
        @media(max-width:600px) { .ai-summary-grid { grid-template-columns:repeat(2,1fr); } .ai-action-grid { flex-direction:column; } }
    `).appendTo('head');
}