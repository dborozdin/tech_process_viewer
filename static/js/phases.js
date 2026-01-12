$(document).ready(function() {
    function updateBreadcrumbs() {
        const params = new URLSearchParams(window.location.search);
        const aircraftId = params.get('aircraftId');
        const aircraftName = params.get('aircraftName');
        const processId = params.get('processId');
        const processName = params.get('processName');

        const breadcrumbs = [
            { name: 'aircrafts', href: '/' }
        ];

        if (aircraftId && aircraftName) {
            breadcrumbs.push({
                name: aircraftName,
                href: `/processes?aircraftId=${aircraftId}&aircraftName=${encodeURIComponent(aircraftName)}`
            });
        }

        if (processId && processName) {
            breadcrumbs.push({
                name: processName,
                href: `/phases?processId=${processId}&processName=${encodeURIComponent(processName)}&aircraftId=${aircraftId}&aircraftName=${encodeURIComponent(aircraftName)}`
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
    // Expose loadPhases for common.js
    function loadPhases(processId) {
        $.ajax({
            url: `/api/phases/${processId}`,
            method: 'GET',
            success: function(data) {
                let tbody = $('#phases-table tbody');
                tbody.empty();
                data.forEach(item => {
                    let row = `<tr class="clickable" data-id="${item.phase_id}" data-name="${item.original_name || item.name}">
                        <td>${item.name}</td>
                        <td>${item.org_unit}</td>
                        <td>${item.process_type || ''}</td>
                    </tr>`;
                    tbody.append(row);
                });
            },
            error: function(xhr, status, error) {
                console.error('Error loading phases:', error);
            }
        });
    };

    // читаем параметры из URL
    const params = new URLSearchParams(window.location.search);
    const processId = params.get('processId');
    const processName = params.get('processName');

    // показываем секцию процессов
    $('#phases-section').removeClass('hidden');

    // если пришёл ID — грузим фазы
    if (processId) {
        navigationState.push({ level: 'phases', name: processName, id: processId });
        updateInterface();
        loadPhases(processId);
    }

    $('#phases-table').on('click', 'tr.clickable', function() {
        let phaseId = $(this).data('id');
        let phaseName = $(this).data('name');
        let processId = params.get('processId');
        let processName = params.get('processName');
        const aircraftId = params.get('aircraftId');
        const aircraftName = params.get('aircraftName');
        newHref=`technical_processes?phaseId=${phaseId}&phaseName=${encodeURIComponent(phaseName)}&processId=${processId}&processName=${encodeURIComponent(processName)}&aircraftId=${aircraftId}&aircraftName=${encodeURIComponent(aircraftName)}`;
        console.log('Trying to open:', newHref)
        window.location.href = newHref
    });



});
