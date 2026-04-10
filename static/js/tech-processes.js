$(document).ready(function() {
    var params = new URLSearchParams(window.location.search);
    var aircraftId = params.get('aircraftId');
    var aircraftName = params.get('aircraftName');
    var processId = params.get('processId');
    var processName = params.get('processName');
    var phaseId = params.get('phaseId');
    var phaseName = params.get('phaseName');
    var modal = new crudUI.CrudModal('tp-modal');

    function updateBreadcrumbs() {
        var breadcrumbs = [{name: 'aircrafts', href: '/'}];
        if (aircraftId && aircraftName)
            breadcrumbs.push({name: aircraftName, href: '/processes?aircraftId=' + aircraftId + '&aircraftName=' + encodeURIComponent(aircraftName)});
        if (processId && processName)
            breadcrumbs.push({name: processName, href: '/phases?processId=' + processId + '&processName=' + encodeURIComponent(processName) + '&aircraftId=' + aircraftId + '&aircraftName=' + encodeURIComponent(aircraftName)});
        if (phaseId && phaseName)
            breadcrumbs.push({name: phaseName, href: '/technical_processes?phaseId=' + phaseId + '&phaseName=' + encodeURIComponent(phaseName) + '&processId=' + processId + '&processName=' + encodeURIComponent(processName) + '&aircraftId=' + aircraftId + '&aircraftName=' + encodeURIComponent(aircraftName)});
        var html = breadcrumbs.map(function(item, i) {
            return i === breadcrumbs.length - 1 ? '<span>' + item.name + '</span>' : '<a href="' + item.href + '">' + item.name + '</a>';
        }).join(' > ');
        $('#breadcrumbs').html(html);
    }
    updateBreadcrumbs();

    // Toolbar
    $('#tech-processes-toolbar').html(crudUI.buildToolbar([
        {label: 'Add Tech Process', className: 'btn-crud btn-add', id: 'btn-add-tp'}
    ]));

    function loadTechnicalProcesses(pid) {
        $.ajax({
            url: '/api/technical_processes/' + pid,
            method: 'GET',
            success: function(data) {
                var tbody = $('#tech-processes-table tbody');
                tbody.empty();
                data.forEach(function(item) {
                    var row = '<tr class="clickable" data-id="' + item.tech_proc_id + '" data-name="' + (item.original_name || item.name || '') + '">' +
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

    $('#tech-processes-section').removeClass('hidden');
    if (phaseId) {
        navigationState.push({level: 'phases', name: phaseName, id: phaseId});
        updateInterface();
        loadTechnicalProcesses(phaseId);
    }

    // Navigate to details
    $('#tech-processes-table').on('click', 'tr.clickable td:not(.actions-cell)', function() {
        var tr = $(this).closest('tr');
        var techProcId = tr.data('id');
        var techProcName = tr.data('name');
        window.location.href = 'technical_process_details?techProcId=' + techProcId +
            '&techProcName=' + encodeURIComponent(techProcName) +
            '&phaseId=' + phaseId + '&phaseName=' + encodeURIComponent(phaseName) +
            '&processId=' + processId + '&processName=' + encodeURIComponent(processName) +
            '&aircraftId=' + aircraftId + '&aircraftName=' + encodeURIComponent(aircraftName);
    });

    // Add tech process
    $('#btn-add-tp').on('click', function() {
        var fields = [
            {name: 'name', label: 'Name', type: 'text', required: true},
            {name: 'id', label: 'Identifier', type: 'text'},
            {name: 'description', label: 'Description', type: 'textarea'}
        ];
        var formHtml = crudUI.buildForm('tp-form', fields);
        var footer = '<button class="btn-crud btn-add" id="tp-save">Create</button>' +
                     '<button class="btn-crud btn-confirm-cancel" id="tp-cancel">Cancel</button>';
        modal.open('New Tech Process', formHtml, footer);

        $('#tp-save').on('click', function() {
            var data = crudUI.getFormData('tp-form');
            if (!data.name) { crudUI.showNotification('Enter name', 'error'); return; }

            $.ajax({
                url: '/api/business-processes',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({name: data.name, id: data.id || data.name, description: data.description}),
                success: function(resp) {
                    if (resp.success) {
                        $.ajax({
                            url: '/api/business-processes/' + phaseId + '/elements',
                            method: 'POST',
                            contentType: 'application/json',
                            data: JSON.stringify({element_id: resp.data.bp_id}),
                            success: function() {
                                crudUI.showNotification('Tech process created', 'success');
                                modal.close();
                                loadTechnicalProcesses(phaseId);
                            },
                            error: function() {
                                crudUI.showNotification('Tech process created but not added to phase', 'error');
                                modal.close();
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
        $('#tp-cancel').on('click', function() { modal.close(); });
    });

    // Edit tech process
    $('#tech-processes-table').on('click', '.btn-icon-edit', function(e) {
        e.stopPropagation();
        var tr = $(this).closest('tr');
        var bpId = tr.data('id');
        var currentName = tr.data('name');

        var fields = [
            {name: 'name', label: 'Name', type: 'text', value: currentName, required: true},
            {name: 'description', label: 'Description', type: 'textarea'}
        ];
        var formHtml = crudUI.buildForm('tp-edit-form', fields);
        var footer = '<button class="btn-crud btn-add" id="tp-edit-save">Save</button>' +
                     '<button class="btn-crud btn-confirm-cancel" id="tp-edit-cancel">Cancel</button>';
        modal.open('Edit Tech Process', formHtml, footer);

        $('#tp-edit-save').on('click', function() {
            var data = crudUI.getFormData('tp-edit-form');
            $.ajax({
                url: '/api/business-processes/' + bpId,
                method: 'PUT',
                contentType: 'application/json',
                data: JSON.stringify(data),
                success: function(resp) {
                    if (resp.success) {
                        crudUI.showNotification('Tech process updated', 'success');
                        modal.close();
                        loadTechnicalProcesses(phaseId);
                    } else {
                        crudUI.showNotification(resp.message || 'Error', 'error');
                    }
                }
            });
        });
        $('#tp-edit-cancel').on('click', function() { modal.close(); });
    });

    // Delete tech process
    $('#tech-processes-table').on('click', '.btn-icon-delete', function(e) {
        e.stopPropagation();
        var tr = $(this).closest('tr');
        var childId = tr.data('id');
        var name = tr.data('name');

        crudUI.confirm('Delete tech process "' + name + '"?').then(function(ok) {
            if (!ok) return;
            $.ajax({
                url: '/api/business-processes/' + phaseId + '/elements/' + childId,
                method: 'DELETE',
                success: function() {
                    $.ajax({
                        url: '/api/business-processes/' + childId,
                        method: 'DELETE',
                        complete: function() {
                            crudUI.showNotification('Tech process deleted', 'success');
                            loadTechnicalProcesses(phaseId);
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
