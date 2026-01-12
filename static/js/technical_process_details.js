$(document).ready(function() {
    function updateBreadcrumbs() {
        const params = new URLSearchParams(window.location.search);
        const aircraftId = params.get('aircraftId');
        const aircraftName = params.get('aircraftName');
        const processId = params.get('processId');
        const processName = params.get('processName');
        const phaseId = params.get('phaseId');
        const phaseName = params.get('phaseName');
        const techProcId = params.get('techProcId');
        const techProcName = params.get('techProcName');

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

        if (techProcId && techProcName) {
            breadcrumbs.push({
                name: techProcName,
                href: `technical_process_details?techProcId=${techProcId}&techProcName=${encodeURIComponent(techProcName)}&phaseId=${phaseId}&phaseName=${encodeURIComponent(phaseName)}&processId=${processId}&processName=${encodeURIComponent(processName)}&aircraftId=${aircraftId}&aircraftName=${encodeURIComponent(aircraftName)}`

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
    function loadTechnicalProcessDetails(techProcessId) {
        $.ajax({
            url: `/api/technical_process_details/${techProcId}`,
            method: 'GET',
            success: function(data) {
                $('#tech-proc-info').html(`
                    <p><strong>Name:</strong> ${data.name}</p>
                    <p><strong>Org Unit:</strong> ${data.org_unit}</p>
                    <p><strong>Process Type:</strong> ${data.process_type}</p>
                `);

                let opsTbody = $('#operations-table tbody');
                opsTbody.empty();
                let stepsContainer = $('#steps-container');
                stepsContainer.empty();
                data.operations.forEach(op => {
                    let opRow = `<tr class="clickable-op" data-id="${op.operation_id}">
                        <td>${op.name}</td>
                        <td>${op.description || ''}</td>
                        <td>${op.man_hours || ''}</td>
                    </tr>`;
                    opsTbody.append(opRow);

                    let stepsHtml = `<div id="steps-${op.operation_id}" class="hidden">
                        <h4>Steps for Operation: ${op.name}</h4>
                        <table>
                            <thead><tr><th>Number</th><th>Name</th><th>Description</th></tr></thead>
                            <tbody>`;
                    op.steps.forEach(step => {
                        stepsHtml += `<tr>
                            <td>${step.number}</td>
                            <td>${step.name}</td>
                            <td>${step.description || ''}</td>
                        </tr>`;
                    });
                    stepsHtml += `</tbody></table></div>`;
                    stepsContainer.append(stepsHtml);
                });

                $('#operations-table').off('click', '.clickable-op').on('click', '.clickable-op', function() {
                    let opId = $(this).data('id');
                    $(`#steps-${opId}`).toggleClass('hidden');
                });

                let docsTbody = $('#documents-table tbody');
                docsTbody.empty();
                data.documents.forEach(doc => {
                    let row = `<tr>
                        <td>${doc.name}</td>
                        <td>${doc.code}</td>
                        <td>${doc.type}</td>
                    </tr>`;
                    docsTbody.append(row);
                });

                let matsTbody = $('#materials-table tbody');
                matsTbody.empty();
                data.materials.forEach(mat => {
                    let row = `<tr>
                        <td>${mat.name}</td>
                        <td>${mat.code}</td>
                        <td>${mat.id}</td>
                        <td>${mat.standart}</td>
                        <td>${mat.uom}</td>
                    </tr>`;
                    matsTbody.append(row);
                });
            },
            error: function(xhr, status, error) {
                console.error('Error loading technical process details:', error);
            }
        });
    }
            // читаем параметры из URL
    const params = new URLSearchParams(window.location.search);
    const techProcId = params.get('techProcId');
    const techProcName = params.get('techProcName');

    // показываем секцию процессов
    $('#details-section').removeClass('hidden');

    // если пришёл ID техпроцесса — грузим детали
    if (techProcId) {
        navigationState.push({ level: 'tech-processes', name: techProcName, id: techProcId });
        updateInterface();
        loadTechnicalProcessDetails(techProcId);
    }
});