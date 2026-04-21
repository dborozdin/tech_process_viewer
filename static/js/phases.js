$(document).ready(function() {
    var params = new URLSearchParams(window.location.search);
    var aircraftId = params.get('aircraftId');
    var aircraftName = params.get('aircraftName');
    var processId = params.get('processId');
    var processName = params.get('processName');
    var modal = new crudUI.CrudModal('phase-modal');

    function updateBreadcrumbs() {
        var breadcrumbs = [{name: 'aircrafts', href: '/'}];
        if (aircraftId && aircraftName)
            breadcrumbs.push({name: aircraftName, href: '/processes?aircraftId=' + aircraftId + '&aircraftName=' + encodeURIComponent(aircraftName)});
        if (processId && processName)
            breadcrumbs.push({name: processName, href: '/phases?processId=' + processId + '&processName=' + encodeURIComponent(processName) + '&aircraftId=' + aircraftId + '&aircraftName=' + encodeURIComponent(aircraftName)});
        var html = breadcrumbs.map(function(item, i) {
            return i === breadcrumbs.length - 1 ? '<span>' + item.name + '</span>' : '<a href="' + item.href + '">' + item.name + '</a>';
        }).join(' > ');
        $('#breadcrumbs').html(html);
    }
    updateBreadcrumbs();

    // Toolbar
    $('#phases-toolbar').html(crudUI.buildToolbar([
        {label: 'Add Phase', className: 'btn-crud btn-add', id: 'btn-add-phase'}
    ]));

    function loadPhases(pid) {
        $.ajax({
            url: '/api/phases/' + pid,
            method: 'GET',
            success: function(data) {
                var tbody = $('#phases-table tbody');
                tbody.empty();
                data.forEach(function(item) {
                    var row = '<tr class="clickable" data-id="' + item.phase_id + '" data-name="' + (item.original_name || item.name || '') + '">' +
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

    $('#phases-section').removeClass('hidden');
    if (processId) {
        navigationState.push({level: 'phases', name: processName, id: processId});
        updateInterface();
        loadPhases(processId);
    }

    // Navigate to tech processes
    $('#phases-table').on('click', 'tr.clickable td:not(.actions-cell)', function() {
        var tr = $(this).closest('tr');
        var phaseId = tr.data('id');
        var phaseName = tr.data('name');
        window.location.href = 'technical_processes?phaseId=' + phaseId +
            '&phaseName=' + encodeURIComponent(phaseName) +
            '&processId=' + processId + '&processName=' + encodeURIComponent(processName) +
            '&aircraftId=' + aircraftId + '&aircraftName=' + encodeURIComponent(aircraftName);
    });

    // Add phase
    $('#btn-add-phase').on('click', function() {
        var fields = [
            {name: 'name', label: 'Name', type: 'text', required: true},
            {name: 'id', label: 'Identifier', type: 'text'},
            {name: 'description', label: 'Description', type: 'textarea'}
        ];
        var formHtml = crudUI.buildForm('phase-form', fields);
        var footer = '<button class="btn-crud btn-add" id="phase-save">Create</button>' +
                     '<button class="btn-crud btn-confirm-cancel" id="phase-cancel">Cancel</button>';
        modal.open('New Phase', formHtml, footer);

        $('#phase-save').on('click', function() {
            var data = crudUI.getFormData('phase-form');
            if (!data.name) { crudUI.showNotification('Enter name', 'error'); return; }

            // Create BP then add as element of parent
            $.ajax({
                url: '/api/business-processes',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({name: data.name, id: data.id || data.name, description: data.description}),
                success: function(resp) {
                    if (resp.success) {
                        $.ajax({
                            url: '/api/business-processes/' + processId + '/elements',
                            method: 'POST',
                            contentType: 'application/json',
                            data: JSON.stringify({element_id: resp.data.bp_id}),
                            success: function() {
                                crudUI.showNotification('Phase created', 'success');
                                modal.close();
                                loadPhases(processId);
                            },
                            error: function() {
                                crudUI.showNotification('Phase created but not added to process', 'error');
                                modal.close();
                                loadPhases(processId);
                            }
                        });
                    } else {
                        crudUI.showNotification(resp.message || 'Error', 'error');
                    }
                },
                error: function(xhr) {
                    crudUI.showNotification(xhr.responseJSON ? xhr.responseJSON.message : 'Error', 'error');
                }
            });
        });
        $('#phase-cancel').on('click', function() { modal.close(); });
    });

    // Edit phase
    $('#phases-table').on('click', '.btn-icon-edit', function(e) {
        e.stopPropagation();
        var tr = $(this).closest('tr');
        var bpId = tr.data('id');
        var currentName = tr.data('name');

        var fields = [
            {name: 'name', label: 'Name', type: 'text', value: currentName, required: true},
            {name: 'description', label: 'Description', type: 'textarea'}
        ];
        var formHtml = crudUI.buildForm('phase-edit-form', fields);
        var footer = '<button class="btn-crud btn-add" id="phase-edit-save">Save</button>' +
                     '<button class="btn-crud btn-confirm-cancel" id="phase-edit-cancel">Cancel</button>';
        modal.open('Edit Phase', formHtml, footer);

        $('#phase-edit-save').on('click', function() {
            var data = crudUI.getFormData('phase-edit-form');
            $.ajax({
                url: '/api/business-processes/' + bpId,
                method: 'PUT',
                contentType: 'application/json',
                data: JSON.stringify(data),
                success: function(resp) {
                    if (resp.success) {
                        crudUI.showNotification('Phase updated', 'success');
                        modal.close();
                        loadPhases(processId);
                    } else {
                        crudUI.showNotification(resp.message || 'Error', 'error');
                    }
                }
            });
        });
        $('#phase-edit-cancel').on('click', function() { modal.close(); });
    });

    // Delete phase
    $('#phases-table').on('click', '.btn-icon-delete', function(e) {
        e.stopPropagation();
        var tr = $(this).closest('tr');
        var childId = tr.data('id');
        var name = tr.data('name');

        crudUI.confirm('Delete phase "' + name + '"?').then(function(ok) {
            if (!ok) return;
            // Remove from parent elements
            $.ajax({
                url: '/api/business-processes/' + processId + '/elements/' + childId,
                method: 'DELETE',
                success: function() {
                    // Then delete the BP itself
                    $.ajax({
                        url: '/api/business-processes/' + childId,
                        method: 'DELETE',
                        complete: function() {
                            crudUI.showNotification('Phase deleted', 'success');
                            loadPhases(processId);
                        }
                    });
                },
                error: function() {
                    crudUI.showNotification('Delete error', 'error');
                }
            });
        });
    });
});
