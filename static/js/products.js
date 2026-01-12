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
    loadAircraftList();
    $('#products-section').removeClass('hidden');

    $('#aircraft-table').on('click', 'tr.clickable', function() {
        let aircraftId = $(this).data('id');
        let aircraftName = $(this).data('name');
        // переходим на страницу процессов, передавая параметры через URL
        newHref= `/processes?aircraftId=${aircraftId}&aircraftName=${encodeURIComponent(aircraftName)}`;
        console.log('Trying to open:', newHref)
        window.location.href = newHref

    });


});
