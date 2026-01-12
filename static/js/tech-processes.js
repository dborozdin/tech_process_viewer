$(document).ready(function() {
    function updateBreadcrumbs() {
        const params = new URLSearchParams(window.location.search);
        const aircraftId = params.get('aircraftId');
        const aircraftName = params.get('aircraftName');
        const processId = params.get('processId');
        const processName = params.get('processName');
        const phaseId = params.get('phaseId');
        const phaseName = params.get('phaseName');

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

        if (phaseId && phaseName) {
            breadcrumbs.push({
                name: phaseName,
                href: `/technical_processes?phaseId=${phaseId}&phaseName=${encodeURIComponent(phaseName)}&processId=${processId}&processName=${encodeURIComponent(processName)}&aircraftId=${aircraftId}&aircraftName=${encodeURIComponent(aircraftName)}`
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
    function loadTechnicalProcesses(phaseId) {
        $.ajax({
            url: `/api/technical_processes/${phaseId}`,
            method: 'GET',
            success: function(data) {
                let tbody = $('#tech-processes-table tbody');
                tbody.empty();
                data.forEach(item => {
                    let row = `<tr class="clickable" data-id="${item.tech_proc_id}" data-name="${item.name}">
                        <td>${item.name}</td>
                        <td>${item.org_unit}</td>
                        <td>${item.process_type}</td>
                    </tr>`;
                    tbody.append(row);
                });
            },
            error: function(xhr, status, error) {
                console.error('Error loading technical processes:', error);
            }
        });
    };
        // читаем параметры из URL
    const params = new URLSearchParams(window.location.search);
    const phaseId = params.get('phaseId');
    const phaseName = params.get('phaseName');

    // показываем секцию процессов
    $('#tech-processes-section').removeClass('hidden');

    // если пришёл ID фазы — грузим техпроцессы
    if (phaseId) {
        navigationState.push({ level: 'phases', name: phaseName, id: phaseId });
        updateInterface();
        loadTechnicalProcesses(phaseId);
    }
    $('#tech-processes-table').on('click', 'tr.clickable', function() {
        let techProcId = $(this).data('id');
        let techProcName = $(this).data('name');
        let phaseId = params.get('phaseId');
        let phaseName = params.get('phaseName');
        let processId = params.get('processId');
        let processName = params.get('processName');
        const aircraftId = params.get('aircraftId');
        const aircraftName = params.get('aircraftName');
        newHref=`technical_process_details?techProcId=${techProcId}&techProcName=${encodeURIComponent(techProcName)}&phaseId=${phaseId}&phaseName=${encodeURIComponent(phaseName)}&processId=${processId}&processName=${encodeURIComponent(processName)}&aircraftId=${aircraftId}&aircraftName=${encodeURIComponent(aircraftName)}`;
        console.log('Trying to open:', newHref)
        window.location.href = newHref
    });

});
