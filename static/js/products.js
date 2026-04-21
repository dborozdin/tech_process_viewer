$(document).ready(function() {

    var selectedRow = null;  // {pdf_id, name, code}
    var clipboard = null;    // {pdf_id, name} for BOM copy-paste
    var modal = new crudUI.CrudModal('product-modal');

    // ========== Toolbar ==========

    $('#products-toolbar').html(crudUI.buildToolbar([
        {label: 'Add Product', className: 'btn-crud btn-add', id: 'btn-add-product'},
        {label: 'Paste as Component', className: 'btn-crud btn-copy', id: 'btn-paste-bom'}
    ]) + '<span id="clipboard-info"></span>');

    // Disable Paste button until a row is selected AND clipboard has content
    function updatePasteButton() {
        var enabled = selectedRow && clipboard;
        $('#btn-paste-bom').prop('disabled', !enabled);
    }
    updatePasteButton();

    // ========== Load Aircraft List ==========

    function loadAircraftList() {
        $.ajax({
            url: '/api/aircraft',
            method: 'GET',
            success: function(data) {
                var tbody = $('#aircraft-table tbody');
                tbody.empty();
                selectedRow = null;
                data.forEach(function(item) {
                    var row = '<tr class="clickable" data-id="' + item.aircraft_id +
                        '" data-name="' + (item.name || '') +
                        '" data-code="' + (item.code || '') + '">' +
                        '<td>' + (item.code || '') + '</td>' +
                        '<td>' + (item.name || '') + '</td>' +
                        '<td>' + (item.data_type || '') + '</td>' +
                        '<td>' + (item.serial_number || '') + '</td>' +
                        '<td>' + (item.release_date || '') + '</td>' +
                        '<td>' + (item.repair_date || '') + '</td>' +
                        '<td class="actions-cell">' +
                        '  <button class="btn-icon-edit" title="Edit">&#9998;</button>' +
                        '  <button class="btn-icon-copy" title="Copy for BOM">&#9776;</button>' +
                        '  <button class="btn-icon-delete" title="Delete">&#10005;</button>' +
                        '</td></tr>';
                    tbody.append(row);
                });
                $('#products-section').show();
            },
            error: function() {
                dbConnection.clearSession();
                $('#products-section').hide();
                $('#db-status').text('DB Status: Disconnected');
            }
        });
    }

    // ========== Selection & Navigation ==========

    // Single click — select row (highlight for BOM operations)
    $('#aircraft-table').on('click', 'tr.clickable td:not(.actions-cell)', function() {
        var tr = $(this).closest('tr');
        $('#aircraft-table tr').removeClass('selected-row');
        tr.addClass('selected-row');
        selectedRow = {
            pdf_id: tr.data('id'),
            name: tr.data('name'),
            code: tr.data('code')
        };
        updatePasteButton();
    });

    // Double click — navigate to processes
    $('#aircraft-table').on('dblclick', 'tr.clickable td:not(.actions-cell)', function() {
        var tr = $(this).closest('tr');
        var aircraftId = tr.data('id');
        var aircraftName = tr.data('name');
        window.location.href = '/processes?aircraftId=' + aircraftId +
            '&aircraftName=' + encodeURIComponent(aircraftName);
    });

    // ========== Add Product ==========

    $('#btn-add-product').on('click', function() {
        var fields = [
            {name: 'id', label: 'Code (designation)', type: 'text', required: true},
            {name: 'name', label: 'Name', type: 'text', required: true}
        ];

        if (selectedRow) {
            fields.push({
                name: 'as_component',
                label: 'Add as component of: ' + (selectedRow.name || selectedRow.code),
                type: 'checkbox',
                value: false
            });
            fields.push({name: 'quantity', label: 'Quantity', type: 'number', value: 1, hidden: true});
        }

        var formHtml = crudUI.buildForm('product-form', fields);
        var footer = '<button class="btn-crud btn-add" id="product-save">Create</button>' +
                     '<button class="btn-crud btn-confirm-cancel" id="product-cancel">Cancel</button>';
        modal.open('New Product', formHtml, footer);

        // Toggle quantity visibility based on checkbox
        if (selectedRow) {
            $(modal.getBody()).on('change', '#product-form-as_component', function() {
                var qtyGroup = $('#product-form-quantity').closest('.form-group');
                if (this.checked) qtyGroup.show(); else qtyGroup.hide();
            });
        }

        $('#product-save').on('click', function() {
            var data = crudUI.getFormData('product-form');
            if (!data.id || !data.name) {
                crudUI.showNotification('Fill in code and name', 'error');
                return;
            }

            $.ajax({
                url: '/api/products',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({id: data.id, name: data.name}),
                success: function(resp) {
                    if (resp.success) {
                        crudUI.showNotification('Product created', 'success');
                        // Create BOM link if requested
                        if (data.as_component && selectedRow) {
                            $.ajax({
                                url: '/api/products/bom',
                                method: 'POST',
                                contentType: 'application/json',
                                data: JSON.stringify({
                                    relating_pdf_id: selectedRow.pdf_id,
                                    related_pdf_id: resp.data.pdf_id,
                                    quantity: data.quantity || 1
                                }),
                                success: function() {
                                    crudUI.showNotification('BOM link created', 'success');
                                }
                            });
                        }
                        modal.close();
                        loadAircraftList();
                    } else {
                        crudUI.showNotification(resp.message || 'Error', 'error');
                    }
                },
                error: function(xhr) {
                    var msg = xhr.responseJSON ? xhr.responseJSON.message : 'Error';
                    crudUI.showNotification(msg, 'error');
                }
            });
        });

        $('#product-cancel').on('click', function() { modal.close(); });
    });

    // ========== Edit Product ==========

    $('#aircraft-table').on('click', '.btn-icon-edit', function(e) {
        e.stopPropagation();
        var tr = $(this).closest('tr');
        var pdfId = tr.data('id');
        var currentName = tr.data('name');
        var currentCode = tr.data('code');

        var fields = [
            {name: 'id', label: 'Code (designation)', type: 'text', value: currentCode},
            {name: 'name', label: 'Name', type: 'text', value: currentName, required: true}
        ];

        var formHtml = crudUI.buildForm('product-edit-form', fields);
        var footer = '<button class="btn-crud btn-add" id="product-edit-save">Save</button>' +
                     '<button class="btn-crud btn-confirm-cancel" id="product-edit-cancel">Cancel</button>';
        modal.open('Edit Product', formHtml, footer);

        $('#product-edit-save').on('click', function() {
            var data = crudUI.getFormData('product-edit-form');
            $.ajax({
                url: '/api/products/' + pdfId,
                method: 'PUT',
                contentType: 'application/json',
                data: JSON.stringify(data),
                success: function(resp) {
                    if (resp.success) {
                        crudUI.showNotification('Product updated', 'success');
                        modal.close();
                        loadAircraftList();
                    } else {
                        crudUI.showNotification(resp.message || 'Error', 'error');
                    }
                },
                error: function(xhr) {
                    crudUI.showNotification(xhr.responseJSON ? xhr.responseJSON.message : 'Error', 'error');
                }
            });
        });

        $('#product-edit-cancel').on('click', function() { modal.close(); });
    });

    // ========== Delete Product ==========

    $('#aircraft-table').on('click', '.btn-icon-delete', function(e) {
        e.stopPropagation();
        var tr = $(this).closest('tr');
        var pdfId = tr.data('id');
        var name = tr.data('name');

        crudUI.confirm('Delete product "' + name + '"?').then(function(ok) {
            if (!ok) return;
            $.ajax({
                url: '/api/products/' + pdfId,
                method: 'DELETE',
                success: function(resp) {
                    if (resp.success) {
                        crudUI.showNotification('Product deleted', 'success');
                        loadAircraftList();
                    } else {
                        crudUI.showNotification(resp.message || 'Error', 'error');
                    }
                },
                error: function(xhr) {
                    crudUI.showNotification(xhr.responseJSON ? xhr.responseJSON.message : 'Error', 'error');
                }
            });
        });
    });

    // ========== Copy for BOM ==========

    $('#aircraft-table').on('click', '.btn-icon-copy', function(e) {
        e.stopPropagation();
        var tr = $(this).closest('tr');
        clipboard = {
            pdf_id: tr.data('id'),
            name: tr.data('name'),
            code: tr.data('code')
        };
        updatePasteButton();
        $('#clipboard-info').html(
            '<span class="clipboard-indicator">Copied: ' + (clipboard.code || clipboard.name) + '</span>'
        );
        crudUI.showNotification('Product copied to clipboard', 'info');
    });

    // ========== Paste as BOM Component ==========

    $('#btn-paste-bom').on('click', function() {
        if (!clipboard) {
            crudUI.showNotification('Copy a product first (Copy button)', 'error');
            return;
        }

        // Need a selected row as parent
        var parentRow = selectedRow;
        if (!parentRow) {
            crudUI.showNotification('Select parent product (right-click on row)', 'error');
            return;
        }

        if (parentRow.pdf_id === clipboard.pdf_id) {
            crudUI.showNotification('Cannot add product as component of itself', 'error');
            return;
        }

        var fields = [
            {name: 'parent', label: 'Parent product', type: 'text', value: parentRow.name || parentRow.code, readonly: true},
            {name: 'component', label: 'Component', type: 'text', value: clipboard.name || clipboard.code, readonly: true},
            {name: 'quantity', label: 'Quantity', type: 'number', value: 1, required: true}
        ];

        var formHtml = crudUI.buildForm('bom-form', fields);
        var footer = '<button class="btn-crud btn-add" id="bom-save">Create link</button>' +
                     '<button class="btn-crud btn-confirm-cancel" id="bom-cancel">Cancel</button>';
        modal.open('Assembly inclusion (BOM)', formHtml, footer);

        // Make parent/component fields readonly
        $('#bom-form-parent, #bom-form-component').prop('readonly', true);

        $('#bom-save').on('click', function() {
            var data = crudUI.getFormData('bom-form');
            $.ajax({
                url: '/api/products/bom',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({
                    relating_pdf_id: parentRow.pdf_id,
                    related_pdf_id: clipboard.pdf_id,
                    quantity: data.quantity || 1
                }),
                success: function(resp) {
                    if (resp.success) {
                        crudUI.showNotification('BOM link created', 'success');
                        modal.close();
                    } else {
                        crudUI.showNotification(resp.message || 'Error', 'error');
                    }
                },
                error: function(xhr) {
                    crudUI.showNotification(xhr.responseJSON ? xhr.responseJSON.message : 'Error', 'error');
                }
            });
        });

        $('#bom-cancel').on('click', function() { modal.close(); });
    });

    // ========== Connection ==========

    function checkConnectionAndLoadAircrafts() {
        dbConnection.initFromCookies();
        $.ajax({
            url: '/api/aircraft',
            method: 'GET',
            success: function() {
                $('#db-status').text(dbConnection.getStatusText());
                loadAircraftList();
            },
            error: function() {
                dbConnection.clearSession();
                $('#db-status').text('DB Status: Disconnected');
                $('#products-section').hide();
            }
        });
    }

    $('#connect-btn').on('click', function() {
        dbConnection.populateDbSelect('#db-select');
        $('#db-modal').show();
    });

    $('.close').on('click', function() { $('#db-modal').hide(); });

    $(window).on('click', function(event) {
        if (event.target == $('#db-modal')[0]) $('#db-modal').hide();
    });

    $('#db-form').on('submit', function(e) {
        e.preventDefault();
        var formData = {
            server_port: $('#server-port').val(),
            db: $('#db-select').val(),
            user: $('#user').val(),
            password: $('#password').val()
        };

        dbConnection.connect(formData)
            .then(function(data) {
                if (data.connected) {
                    $('#db-status').text(dbConnection.getStatusText());
                    $('#products-section').show();
                    $('#db-modal').hide();
                    loadAircraftList();
                } else {
                    $('#db-status').text('DB Status: Connection Failed - ' + data.message);
                    $('#db-modal').hide();
                }
            })
            .catch(function(error) {
                $('#db-status').text('DB Status: Connection Failed');
                console.error('Error connecting to DB:', error);
                $('#db-modal').hide();
            });
    });

    checkConnectionAndLoadAircrafts();
});
