$(document).ready(function() {
    var params = new URLSearchParams(window.location.search);
    var aircraftId = params.get('aircraftId');
    var aircraftName = params.get('aircraftName');
    var modal = new crudUI.CrudModal('process-modal');

    function updateBreadcrumbs() {
        var breadcrumbs = [{name: 'aircrafts', href: '/'}];
        if (aircraftId && aircraftName) {
            breadcrumbs.push({
                name: aircraftName,
                href: '/processes?aircraftId=' + aircraftId + '&aircraftName=' + encodeURIComponent(aircraftName)
            });
        }
        var html = breadcrumbs.map(function(item, index) {
            if (index === breadcrumbs.length - 1) return '<span>' + item.name + '</span>';
            return '<a href="' + item.href + '">' + item.name + '</a>';
        }).join(' > ');
        $('#breadcrumbs').html(html);
    }
    updateBreadcrumbs();

    // Toolbar
    $('#processes-toolbar').html(crudUI.buildToolbar([
        {label: 'Add Process', className: 'btn-crud btn-add', id: 'btn-add-process'}
    ]));

    function loadProcesses(aid) {
        $.ajax({
            url: '/api/processes/' + aid,
            method: 'GET',
            success: function(data) {
                var tbody = $('#processes-table tbody');
                tbody.empty();
                data.forEach(function(item) {
                    var row = '<tr class="clickable" data-id="' + item.process_id + '" data-name="' + (item.name || '') + '">' +
                        '<td>' + (item.name || '') + '</td>' +
                        '<td>' + (item.org_unit || '') + '</td>' +
                        '<td>' + (item.process_type || '') + '</td>' +
                        '<td class="actions-cell">' +
                        '  <button class="btn-icon-edit" title="Edit">&#9998;</button>' +
                        '  <button class="btn-icon-delete" title="Delete">&#10005;</button>' +
                        '</td></tr>';
                    tbody.append(row);
                });
            }
        });
    }

    $('#processes-section').removeClass('hidden');
    if (aircraftId) {
        navigationState.push({level: 'processes', name: aircraftName, id: aircraftId});
        updateInterface();
        loadProcesses(aircraftId);
    }

    // Navigate to phases
    $('#processes-table').on('click', 'tr.clickable td:not(.actions-cell)', function() {
        var tr = $(this).closest('tr');
        var processId = tr.data('id');
        var processName = tr.data('name');
        window.location.href = 'phases?processId=' + processId +
            '&processName=' + encodeURIComponent(processName) +
            '&aircraftId=' + aircraftId +
            '&aircraftName=' + encodeURIComponent(aircraftName);
    });

    // Add process
    $('#btn-add-process').on('click', function() {
        var fields = [
            {name: 'name', label: 'Name', type: 'text', required: true},
            {name: 'id', label: 'Identifier', type: 'text'},
            {name: 'description', label: 'Description', type: 'textarea'}
        ];
        var formHtml = crudUI.buildForm('process-form', fields);
        var footer = '<button class="btn-crud btn-add" id="process-save">Create</button>' +
                     '<button class="btn-crud btn-confirm-cancel" id="process-cancel">Cancel</button>';
        modal.open('New Process', formHtml, footer);

        $('#process-save').on('click', function() {
            var data = crudUI.getFormData('process-form');
            if (!data.name) { crudUI.showNotification('Enter name', 'error'); return; }

            $.ajax({
                url: '/api/business-processes',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({name: data.name, id: data.id || data.name, description: data.description}),
                success: function(resp) {
                    if (resp.success && aircraftId) {
                        // Link to product
                        $.ajax({
                            url: '/api/business-processes/' + resp.data.bp_id + '/link-product',
                            method: 'POST',
                            contentType: 'application/json',
                            data: JSON.stringify({pdf_id: parseInt(aircraftId)}),
                            complete: function() {
                                crudUI.showNotification('Process created', 'success');
                                modal.close();
                                loadProcesses(aircraftId);
                            }
                        });
                    } else if (resp.success) {
                        crudUI.showNotification('Process created', 'success');
                        modal.close();
                        loadProcesses(aircraftId);
                    } else {
                        crudUI.showNotification(resp.message || 'Error', 'error');
                    }
                },
                error: function(xhr) {
                    crudUI.showNotification(xhr.responseJSON ? xhr.responseJSON.message : 'Error', 'error');
                }
            });
        });
        $('#process-cancel').on('click', function() { modal.close(); });
    });

    // Edit process
    $('#processes-table').on('click', '.btn-icon-edit', function(e) {
        e.stopPropagation();
        var tr = $(this).closest('tr');
        var bpId = tr.data('id');
        var currentName = tr.data('name');

        var fields = [
            {name: 'name', label: 'Name', type: 'text', value: currentName, required: true},
            {name: 'description', label: 'Description', type: 'textarea'}
        ];
        var formHtml = crudUI.buildForm('process-edit-form', fields);
        var footer = '<button class="btn-crud btn-add" id="process-edit-save">Save</button>' +
                     '<button class="btn-crud btn-confirm-cancel" id="process-edit-cancel">Cancel</button>';
        modal.open('Edit Process', formHtml, footer);

        $('#process-edit-save').on('click', function() {
            var data = crudUI.getFormData('process-edit-form');
            $.ajax({
                url: '/api/business-processes/' + bpId,
                method: 'PUT',
                contentType: 'application/json',
                data: JSON.stringify(data),
                success: function(resp) {
                    if (resp.success) {
                        crudUI.showNotification('Process updated', 'success');
                        modal.close();
                        loadProcesses(aircraftId);
                    } else {
                        crudUI.showNotification(resp.message || 'Error', 'error');
                    }
                }
            });
        });
        $('#process-edit-cancel').on('click', function() { modal.close(); });
    });

    // Delete process
    $('#processes-table').on('click', '.btn-icon-delete', function(e) {
        e.stopPropagation();
        var tr = $(this).closest('tr');
        var bpId = tr.data('id');
        var name = tr.data('name');

        crudUI.confirm('Delete process "' + name + '"?').then(function(ok) {
            if (!ok) return;
            $.ajax({
                url: '/api/business-processes/' + bpId,
                method: 'DELETE',
                success: function(resp) {
                    if (resp.success) {
                        crudUI.showNotification('Process deleted', 'success');
                        loadProcesses(aircraftId);
                    } else {
                        crudUI.showNotification(resp.message || 'Error', 'error');
                    }
                }
            });
        });
    });

    window.loadProcesses = loadProcesses;
});
