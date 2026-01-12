$(document).ready(function() {
    function loadAircraftList() {
        // Load Aircraft List
        $.ajax({
            url: '/api/aircraft',
            method: 'GET',
            success: function(data) {
                let tbody = $('#aircraft-table tbody');
                tbody.empty();
                data.forEach(item => {
                    console.log('item:', item)
                    let row = `<tr class="clickable" data-id="${item.aircraft_id}" data-name="${item.name}">
                        <td>${item.code}</td>
                        <td>${item.name}</td>
                        <td>${item.data_type}</td>
                        <td>${item.serial_number || ''}</td>
                        <td>${item.release_date || ''}</td>
                        <td>${item.repair_date || ''}</td>
                    </tr>`;
                    tbody.append(row);
                });
            },
            error: function(xhr, status, error) {
                console.error('Error loading aircraft:', error);
            }
        });
    }

    function loadDBList() {
        $.ajax({
            url: '/api/dblist',
            method: 'GET',
            success: function(data) {
                let select = $('#db-select');
                select.empty();
                if (data && data.databases) {
                    data.databases.forEach(db => {
                        let option = `<option value="${db}">${db}</option>`;
                        select.append(option);
                    });
                } else {
                    // Fallback to default
                    select.append('<option value="pss_moma_08_07_2025">pss_moma_08_07_2025</option>');
                }
            },
            error: function(xhr, status, error) {
                console.error('Error loading DB list:', error);
                // Fallback
                $('#db-select').html('<option value="pss_moma_08_07_2025">pss_moma_08_07_2025</option>');
            }
        });
    }

    $('#connect-btn').on('click', function() {
        loadDBList();
        $('#db-modal').show();
    });

    $('.close').on('click', function() {
        $('#db-modal').hide();
    });

    $(window).on('click', function(event) {
        if (event.target == $('#db-modal')[0]) {
            $('#db-modal').hide();
        }
    });

    $('#db-form').on('submit', function(e) {
        e.preventDefault();
        let formData = {
            server_port: $('#server-port').val(),
            db: $('#db-select').val(),
            user: $('#user').val(),
            password: $('#password').val()
        };

        $.ajax({
            url: '/api/connect',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(formData),
            success: function(data) {
                if (data.connected) {
                    $('#db-status').text(`DB: ${data.db} User: ${data.user}`);
                    $('#products-section').show();
                    $('#db-modal').hide();
                    loadAircraftList();
                } else {
                    $('#db-status').text('DB Status: Connection Failed - ' + data.message);
                    $('#db-modal').hide();
                }
            },
            error: function(xhr, status, error) {
                $('#db-status').text('DB Status: Connection Failed');
                console.error('Error connecting to DB:', error);
                $('#db-modal').hide();
            }
        });
    });

    $('#aircraft-table').on('click', 'tr.clickable', function() {
        let aircraftId = $(this).data('id');
        let aircraftName = $(this).data('name');
        // переходим на страницу процессов, передавая параметры через URL
        newHref= `/processes?aircraftId=${aircraftId}&aircraftName=${encodeURIComponent(aircraftName)}`;
        console.log('Trying to open:', newHref)
        window.location.href = newHref

    });


});
