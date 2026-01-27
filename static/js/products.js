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
                $('#products-section').show();
            },
            error: function(xhr, status, error) {
                console.error('Error loading aircraft:', error);
                // If connection is lost, clear stored connection info and hide products section
                dbConnection.clearSession();
                $('#products-section').hide();
                $('#db-status').text('DB Status: Disconnected');
            }
        });
    }

    // Check if already connected on page load
    function checkConnectionAndLoadAircrafts() {
        // First try to restore session from cookies
        dbConnection.initFromCookies();

        $.ajax({
            url: '/api/aircraft',
            method: 'GET',
            success: function(data) {
                // If we can fetch aircrafts, connection is active
                $('#db-status').text(dbConnection.getStatusText());
                loadAircraftList();
            },
            error: function(xhr, status, error) {
                // Connection not active, clear stored connection info
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

    $('#aircraft-table').on('click', 'tr.clickable', function() {
        let aircraftId = $(this).data('id');
        let aircraftName = $(this).data('name');
        // переходим на страницу процессов, передавая параметры через URL
        newHref= `/processes?aircraftId=${aircraftId}&aircraftName=${encodeURIComponent(aircraftName)}`;
        console.log('Trying to open:', newHref)
        window.location.href = newHref

    });

    // Check connection status on page load
    checkConnectionAndLoadAircrafts();


});
