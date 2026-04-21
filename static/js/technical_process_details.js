$(document).ready(function() {
    var params = new URLSearchParams(window.location.search);
    var aircraftId = params.get('aircraftId');
    var aircraftName = params.get('aircraftName');
    var processId = params.get('processId');
    var processName = params.get('processName');
    var phaseId = params.get('phaseId');
    var phaseName = params.get('phaseName');
    var techProcId = params.get('techProcId');
    var techProcName = params.get('techProcName');
    var modal = new crudUI.CrudModal('details-modal');

    function updateBreadcrumbs() {
        var breadcrumbs = [{name: 'aircrafts', href: '/'}];
        if (aircraftId && aircraftName)
            breadcrumbs.push({name: aircraftName, href: '/processes?aircraftId=' + aircraftId + '&aircraftName=' + encodeURIComponent(aircraftName)});
        if (processId && processName)
            breadcrumbs.push({name: processName, href: '/phases?processId=' + processId + '&processName=' + encodeURIComponent(processName) + '&aircraftId=' + aircraftId + '&aircraftName=' + encodeURIComponent(aircraftName)});
        if (phaseId && phaseName)
            breadcrumbs.push({name: phaseName, href: '/technical_processes?phaseId=' + phaseId + '&phaseName=' + encodeURIComponent(phaseName) + '&processId=' + processId + '&processName=' + encodeURIComponent(processName) + '&aircraftId=' + aircraftId + '&aircraftName=' + encodeURIComponent(aircraftName)});
        if (techProcId && techProcName)
            breadcrumbs.push({name: techProcName});
        var html = breadcrumbs.map(function(item, i) {
            if (!item.href || i === breadcrumbs.length - 1) return '<span>' + item.name + '</span>';
            return '<a href="' + item.href + '">' + item.name + '</a>';
        }).join(' > ');
        $('#breadcrumbs').html(html);
    }
    updateBreadcrumbs();

    // ========== Toolbars ==========

    $('#operations-toolbar').html(crudUI.buildToolbar([
        {label: 'Add Operation', className: 'btn-crud btn-add', id: 'btn-add-operation'}
    ]));

    $('#documents-toolbar').html(crudUI.buildToolbar([
        {label: 'Upload Document', className: 'btn-crud btn-add', id: 'btn-upload-doc'},
        {label: 'Attach Existing', className: 'btn-crud btn-secondary', id: 'btn-attach-doc'}
    ]));

    $('#characteristics-toolbar').html(crudUI.buildToolbar([
        {label: 'Add Characteristic', className: 'btn-crud btn-add', id: 'btn-add-char'}
    ]));

    // ========== Load Details ==========

    function loadTechnicalProcessDetails() {
        $.ajax({
            url: '/api/technical_process_details/' + techProcId,
            method: 'GET',
            success: function(data) {
                // Process info
                $('#tech-proc-info').html(
                    '<p><strong>Name:</strong> ' + data.name + '</p>' +
                    '<p><strong>Org Unit:</strong> ' + data.org_unit + '</p>' +
                    '<p><strong>Process Type:</strong> ' + data.process_type + '</p>'
                );

                // Operations
                var opsTbody = $('#operations-table tbody');
                opsTbody.empty();
                var stepsContainer = $('#steps-container');
                stepsContainer.empty();
                (data.operations || []).forEach(function(op) {
                    var opRow = '<tr class="clickable-op" data-id="' + op.operation_id + '" data-name="' + (op.original_name || op.name || '') + '">' +
                        '<td>' + (op.name || '') + '</td>' +
                        '<td>' + (op.description || '') + '</td>' +
                        '<td>' + (op.man_hours || '') + '</td>' +
                        '<td class="actions-cell">' +
                        '  <button class="btn-icon-edit btn-edit-op" title="Edit">&#9998;</button>' +
                        '  <button class="btn-icon-delete btn-delete-op" title="Delete">&#10005;</button>' +
                        '</td></tr>';
                    opsTbody.append(opRow);

                    var stepsHtml = '<div id="steps-' + op.operation_id + '" class="hidden">' +
                        '<h4>Steps for Operation: ' + (op.name || '') + '</h4>' +
                        '<table><thead><tr><th>Number</th><th>Name</th><th>Description</th></tr></thead><tbody>';
                    (op.steps || []).forEach(function(step) {
                        stepsHtml += '<tr><td>' + (step.number || '') + '</td><td>' + (step.name || '') + '</td><td>' + (step.description || '') + '</td></tr>';
                    });
                    stepsHtml += '</tbody></table></div>';
                    stepsContainer.append(stepsHtml);
                });

                // Toggle steps on operation click (not actions)
                $('#operations-table').off('click', '.clickable-op td:not(.actions-cell)').on('click', '.clickable-op td:not(.actions-cell)', function() {
                    var opId = $(this).closest('tr').data('id');
                    $('#steps-' + opId).toggleClass('hidden');
                });

                // Documents
                var docsTbody = $('#documents-table tbody');
                docsTbody.empty();
                (data.documents || []).forEach(function(doc) {
                    var row = '<tr data-ref-id="' + (doc.ref_id || '') + '" data-doc-id="' + (doc.doc_sys_id || '') + '">' +
                        '<td>' + (doc.name || '') + '</td>' +
                        '<td>' + (doc.code || '') + '</td>' +
                        '<td>' + (doc.type || '') + '</td>' +
                        '<td class="actions-cell">' +
                        '  <button class="btn-icon-detach btn-detach-doc" title="Detach">&#10005;</button>' +
                        '</td></tr>';
                    docsTbody.append(row);
                });

                // Materials (read-only)
                var matsTbody = $('#materials-table tbody');
                matsTbody.empty();
                (data.materials || []).forEach(function(mat) {
                    var row = '<tr>' +
                        '<td>' + (mat.name || '') + '</td>' +
                        '<td>' + (mat.code || '') + '</td>' +
                        '<td>' + (mat.id || '') + '</td>' +
                        '<td>' + (mat.quantity || '') + '</td>' +
                        '<td>' + (mat.uom || '') + '</td></tr>';
                    matsTbody.append(row);
                });

                // Characteristics
                var charsTbody = $('#characteristics-table tbody');
                charsTbody.empty();
                (data.characteristics || []).forEach(function(ch) {
                    var row = '<tr data-id="' + ch.sys_id + '" data-subtype="' + (ch.subtype || '') + '" data-char-id="' + (ch.characteristic_id || '') + '">' +
                        '<td>' + (ch.characteristic_name || '') + '</td>' +
                        '<td>' + (ch.value || '') + '</td>' +
                        '<td>' + (ch.unit || '') + '</td>' +
                        '<td class="actions-cell">' +
                        '  <button class="btn-icon-edit btn-edit-char" title="Edit">&#9998;</button>' +
                        '  <button class="btn-icon-delete btn-delete-char" title="Delete">&#10005;</button>' +
                        '</td></tr>';
                    charsTbody.append(row);
                });
            },
            error: function() {
                console.error('Error loading technical process details');
            }
        });
    }

    // ========== Operations CRUD ==========

    // Add operation
    $('#btn-add-operation').on('click', function() {
        var fields = [
            {name: 'name', label: 'Name', type: 'text', required: true},
            {name: 'id', label: 'Identifier', type: 'text'},
            {name: 'description', label: 'Description', type: 'textarea'}
        ];
        var formHtml = crudUI.buildForm('op-form', fields);
        var footer = '<button class="btn-crud btn-add" id="op-save">Create</button>' +
                     '<button class="btn-crud btn-confirm-cancel" id="op-cancel">Cancel</button>';
        modal.open('New Operation', formHtml, footer);

        $('#op-save').on('click', function() {
            var data = crudUI.getFormData('op-form');
            if (!data.name) { crudUI.showNotification('Enter name', 'error'); return; }
            $.ajax({
                url: '/api/business-processes',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({name: data.name, id: data.id || data.name, description: data.description}),
                success: function(resp) {
                    if (resp.success) {
                        $.ajax({
                            url: '/api/business-processes/' + techProcId + '/elements',
                            method: 'POST',
                            contentType: 'application/json',
                            data: JSON.stringify({element_id: resp.data.bp_id}),
                            success: function() {
                                crudUI.showNotification('Operation created', 'success');
                                modal.close();
                                loadTechnicalProcessDetails();
                            },
                            error: function() {
                                crudUI.showNotification('Operation created but not added', 'error');
                                modal.close();
                            }
                        });
                    } else {
                        crudUI.showNotification(resp.message || 'Error', 'error');
                    }
                }
            });
        });
        $('#op-cancel').on('click', function() { modal.close(); });
    });

    // Edit operation
    $('#operations-table').on('click', '.btn-edit-op', function(e) {
        e.stopPropagation();
        var tr = $(this).closest('tr');
        var opId = tr.data('id');
        var currentName = tr.data('name');

        var fields = [
            {name: 'name', label: 'Name', type: 'text', value: currentName, required: true},
            {name: 'description', label: 'Description', type: 'textarea'}
        ];
        var formHtml = crudUI.buildForm('op-edit-form', fields);
        var footer = '<button class="btn-crud btn-add" id="op-edit-save">Save</button>' +
                     '<button class="btn-crud btn-confirm-cancel" id="op-edit-cancel">Cancel</button>';
        modal.open('Edit Operation', formHtml, footer);

        $('#op-edit-save').on('click', function() {
            var data = crudUI.getFormData('op-edit-form');
            $.ajax({
                url: '/api/business-processes/' + opId,
                method: 'PUT',
                contentType: 'application/json',
                data: JSON.stringify(data),
                success: function(resp) {
                    if (resp.success) {
                        crudUI.showNotification('Operation updated', 'success');
                        modal.close();
                        loadTechnicalProcessDetails();
                    }
                }
            });
        });
        $('#op-edit-cancel').on('click', function() { modal.close(); });
    });

    // Delete operation
    $('#operations-table').on('click', '.btn-delete-op', function(e) {
        e.stopPropagation();
        var tr = $(this).closest('tr');
        var opId = tr.data('id');
        var name = tr.data('name');

        crudUI.confirm('Delete operation "' + name + '"?').then(function(ok) {
            if (!ok) return;
            $.ajax({
                url: '/api/business-processes/' + techProcId + '/elements/' + opId,
                method: 'DELETE',
                success: function() {
                    $.ajax({
                        url: '/api/business-processes/' + opId,
                        method: 'DELETE',
                        complete: function() {
                            crudUI.showNotification('Operation deleted', 'success');
                            loadTechnicalProcessDetails();
                        }
                    });
                }
            });
        });
    });

    // ========== Documents CRUD ==========

    // Upload document from disk
    $('#btn-upload-doc').on('click', function() {
        var fields = [
            {name: 'file', label: 'File', type: 'file', required: true},
            {name: 'doc_id', label: 'Document code', type: 'text'},
            {name: 'doc_name', label: 'Name', type: 'text'}
        ];
        var formHtml = crudUI.buildForm('doc-upload-form', fields);
        var footer = '<button class="btn-crud btn-add" id="doc-upload-save">Upload</button>' +
                     '<button class="btn-crud btn-confirm-cancel" id="doc-upload-cancel">Cancel</button>';
        modal.open('Upload Document', formHtml, footer);

        $('#doc-upload-save').on('click', function() {
            var fileInput = document.getElementById('doc-upload-form-file');
            if (!fileInput.files[0]) {
                crudUI.showNotification('Select a file', 'error');
                return;
            }

            var formData = new FormData();
            formData.append('file', fileInput.files[0]);
            formData.append('doc_id', $('#doc-upload-form-doc_id').val() || fileInput.files[0].name);
            formData.append('doc_name', $('#doc-upload-form-doc_name').val() || fileInput.files[0].name);
            formData.append('item_id', techProcId);
            formData.append('item_type', 'apl_business_process');

            $.ajax({
                url: '/api/documents/upload',
                method: 'POST',
                data: formData,
                processData: false,
                contentType: false,
                success: function(resp) {
                    if (resp.success) {
                        crudUI.showNotification('Document uploaded', 'success');
                        modal.close();
                        loadTechnicalProcessDetails();
                    } else {
                        crudUI.showNotification(resp.message || 'Error', 'error');
                    }
                },
                error: function(xhr) {
                    crudUI.showNotification(xhr.responseJSON ? xhr.responseJSON.message : 'Upload error', 'error');
                }
            });
        });
        $('#doc-upload-cancel').on('click', function() { modal.close(); });
    });

    // Attach existing document
    $('#btn-attach-doc').on('click', function() {
        var fields = [
            {name: 'search', label: 'Search by document code', type: 'text', placeholder: 'Enter code...'}
        ];
        var formHtml = crudUI.buildForm('doc-search-form', fields) +
            '<div id="doc-search-results" style="max-height:200px;overflow-y:auto;margin-top:10px"></div>';
        var footer = '<button class="btn-crud btn-confirm-cancel" id="doc-attach-cancel">Close</button>';
        modal.open('Attach Existing Document', formHtml, footer);

        var searchTimer;
        $(modal.getBody()).on('input', '#doc-search-form-search', function() {
            var q = $(this).val();
            clearTimeout(searchTimer);
            if (q.length < 2) { $('#doc-search-results').empty(); return; }
            searchTimer = setTimeout(function() {
                $.ajax({
                    url: '/api/documents/search?q=' + encodeURIComponent(q),
                    method: 'GET',
                    success: function(resp) {
                        var html = '';
                        (resp.data || []).forEach(function(doc) {
                            html += '<div style="padding:6px;border-bottom:1px solid #eee;cursor:pointer" class="doc-search-item" data-doc-id="' + doc.sys_id + '">' +
                                '<strong>' + (doc.doc_id || '') + '</strong> — ' + (doc.name || '') +
                                '</div>';
                        });
                        if (!html) html = '<p style="color:#999;padding:6px">Nothing found</p>';
                        $('#doc-search-results').html(html);
                    }
                });
            }, 300);
        });

        $(modal.getBody()).on('click', '.doc-search-item', function() {
            var docSysId = $(this).data('doc-id');
            $.ajax({
                url: '/api/document-references',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({doc_id: docSysId, item_id: parseInt(techProcId), item_type: 'apl_business_process'}),
                success: function(resp) {
                    if (resp.success) {
                        crudUI.showNotification('Document attached', 'success');
                        modal.close();
                        loadTechnicalProcessDetails();
                    } else {
                        crudUI.showNotification(resp.message || 'Error', 'error');
                    }
                }
            });
        });

        $('#doc-attach-cancel').on('click', function() { modal.close(); });
    });

    // Detach document
    $('#documents-table').on('click', '.btn-detach-doc', function(e) {
        e.stopPropagation();
        var tr = $(this).closest('tr');
        var refId = tr.data('ref-id');

        if (!refId) {
            crudUI.showNotification('Cannot detach (no ref_id)', 'error');
            return;
        }

        crudUI.confirm('Detach document?').then(function(ok) {
            if (!ok) return;
            $.ajax({
                url: '/api/document-references/' + refId,
                method: 'DELETE',
                success: function(resp) {
                    if (resp.success) {
                        crudUI.showNotification('Document detached', 'success');
                        loadTechnicalProcessDetails();
                    }
                }
            });
        });
    });

    // ========== Characteristics CRUD ==========

    // Add characteristic
    $('#btn-add-char').on('click', function() {
        // Load characteristic definitions for dropdown
        $.ajax({
            url: '/api/characteristics',
            method: 'GET',
            success: function(resp) {
                var options = (resp.data || []).map(function(ch) {
                    return {value: ch.sys_id, label: ch.name || ch.id};
                });
                var fields = [
                    {name: 'characteristic_id', label: 'Characteristic', type: 'select', options: options, required: true},
                    {name: 'value', label: 'Value', type: 'text', required: true}
                ];
                var formHtml = crudUI.buildForm('char-form', fields);
                var footer = '<button class="btn-crud btn-add" id="char-save">Create</button>' +
                             '<button class="btn-crud btn-confirm-cancel" id="char-cancel">Cancel</button>';
                modal.open('Add Characteristic', formHtml, footer);

                $('#char-save').on('click', function() {
                    var data = crudUI.getFormData('char-form');
                    if (!data.characteristic_id || !data.value) {
                        crudUI.showNotification('Fill in all fields', 'error');
                        return;
                    }
                    $.ajax({
                        url: '/api/characteristics/values',
                        method: 'POST',
                        contentType: 'application/json',
                        data: JSON.stringify({
                            item_id: parseInt(techProcId),
                            characteristic_id: parseInt(data.characteristic_id),
                            value: data.value
                        }),
                        success: function(resp) {
                            if (resp.success) {
                                crudUI.showNotification('Characteristic added', 'success');
                                modal.close();
                                loadTechnicalProcessDetails();
                            } else {
                                crudUI.showNotification(resp.message || 'Error', 'error');
                            }
                        }
                    });
                });
                $('#char-cancel').on('click', function() { modal.close(); });
            }
        });
    });

    // Edit characteristic
    $('#characteristics-table').on('click', '.btn-edit-char', function(e) {
        e.stopPropagation();
        var tr = $(this).closest('tr');
        var valId = tr.data('id');
        var subtype = tr.data('subtype');
        var currentValue = tr.find('td:eq(1)').text();
        var charName = tr.find('td:eq(0)').text();

        var fields = [
            {name: 'value', label: 'Value (' + charName + ')', type: 'text', value: currentValue, required: true}
        ];
        var formHtml = crudUI.buildForm('char-edit-form', fields);
        var footer = '<button class="btn-crud btn-add" id="char-edit-save">Save</button>' +
                     '<button class="btn-crud btn-confirm-cancel" id="char-edit-cancel">Cancel</button>';
        modal.open('Edit Characteristic', formHtml, footer);

        $('#char-edit-save').on('click', function() {
            var data = crudUI.getFormData('char-edit-form');
            $.ajax({
                url: '/api/characteristics/values/' + valId,
                method: 'PUT',
                contentType: 'application/json',
                data: JSON.stringify({value: data.value, subtype: subtype}),
                success: function(resp) {
                    if (resp.success) {
                        crudUI.showNotification('Characteristic updated', 'success');
                        modal.close();
                        loadTechnicalProcessDetails();
                    }
                }
            });
        });
        $('#char-edit-cancel').on('click', function() { modal.close(); });
    });

    // Delete characteristic
    $('#characteristics-table').on('click', '.btn-delete-char', function(e) {
        e.stopPropagation();
        var tr = $(this).closest('tr');
        var valId = tr.data('id');
        var charName = tr.find('td:eq(0)').text();

        crudUI.confirm('Delete characteristic "' + charName + '"?').then(function(ok) {
            if (!ok) return;
            $.ajax({
                url: '/api/characteristics/values/' + valId,
                method: 'DELETE',
                success: function(resp) {
                    if (resp.success) {
                        crudUI.showNotification('Characteristic deleted', 'success');
                        loadTechnicalProcessDetails();
                    }
                }
            });
        });
    });

    // ========== Init ==========

    $('#details-section').removeClass('hidden');
    if (techProcId) {
        navigationState.push({level: 'tech-processes', name: techProcName, id: techProcId});
        updateInterface();
        loadTechnicalProcessDetails();
    }
});
