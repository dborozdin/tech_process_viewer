$(document).ready(function() {
    function updateBreadcrumbs() {
        const params = new URLSearchParams(window.location.search);
        const aircraftId = params.get('aircraftId');
        const aircraftName = params.get('aircraftName');

        const breadcrumbs = [
            { name: 'aircrafts', href: '/' }
        ];

        if (aircraftId && aircraftName) {
            breadcrumbs.push({
                name: aircraftName,
                href: `/processes?aircraftId=${aircraftId}&aircraftName=${encodeURIComponent(aircraftName)}`
            });
        }

        const $breadcrumbs = $('#breadcrumbs');
        if ($breadcrumbs.length) {
            const html = breadcrumbs.map((item, index) => {
                if (index === breadcrumbs.length - 1) return `<span>${item.name}</span>`;
                else return `<a href="${item.href}">${item.name}</a>`;
            }).join(' > ');
            $breadcrumbs.html(html);
        }
    }
    updateBreadcrumbs();
    // Определяем функцию ДО того, как вызываем её
    function loadProcesses(aircraftId) {
        $.ajax({
            url: `/api/processes/${aircraftId}`,
            method: 'GET',
            success: function(data) {
                let tbody = $('#processes-table tbody');
                tbody.empty();
                data.forEach(item => {
                    let row = `<tr class="clickable" data-id="${item.process_id}" data-name="${item.name}">
                        <td>${item.name}</td>
                        <td>${item.org_unit}</td>
                        <td>${item.process_type}</td>
                    </tr>`;
                    tbody.append(row);
                });
            },
            error: function(xhr, status, error) {
                console.error('Error loading processes:', error);
            }
        });
    }
    // читаем параметры из URL
    const params = new URLSearchParams(window.location.search);
    const aircraftId = params.get('aircraftId');
    const aircraftName = params.get('aircraftName');

    // показываем секцию процессов
    $('#processes-section').removeClass('hidden');

    // если пришёл ID — грузим процессы
    if (aircraftId) {
        navigationState.push({ level: 'processes', name: aircraftName, id: aircraftId });
        updateInterface();
        loadProcesses(aircraftId);
    }


    $('#processes-table').on('click', 'tr.clickable', function() {
        let processId = $(this).data('id');
        let processName = $(this).data('name');
        const aircraftId = params.get('aircraftId');
        const aircraftName = params.get('aircraftName');
        newHref=`phases?processId=${processId}&processName=${encodeURIComponent(processName)}&aircraftId=${aircraftId}&aircraftName=${encodeURIComponent(aircraftName)}`;
        console.log('Trying to open:', newHref)
        window.location.href = newHref
    });

    window.loadProcesses= loadProcesses

});
