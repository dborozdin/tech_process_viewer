$(document).ready(function() {
    // Store navigation state for breadcrumbs (можно использовать, если нужна внутренняя навигация)
    let navigationState = [
        { level: 'products', name: 'aircrafts', id: null }
    ];

    // Функция обновления интерфейса (здесь можно добавить секции и т.д.)
    function updateInterface() {
        console.log('Updating interface with navigationState:', navigationState);
        //updateBreadcrumbs(); // вызываем отдельную функцию
    }

    // Функция построения хлебных крошек для мульти-страничного приложения
    /*
    function updateBreadcrumbs() {
        const params = new URLSearchParams(window.location.search);
        const path = window.location.pathname;

        let breadcrumbs = [];
        breadcrumbs.push({ name: 'aircrafts', href: '/' });

        if (path.startsWith('/processes')) {
            const aircraftId = params.get('aircraftId');
            const aircraftName = params.get('aircraftName');
            if (aircraftId && aircraftName) {
                breadcrumbs.push({
                    name: aircraftName,
                    href: `/processes?aircraftId=${aircraftId}&aircraftName=${encodeURIComponent(aircraftName)}`
                });
            }
        }

        if (path.startsWith('/phases')) {
            const aircraftId = params.get('aircraftId');
            const aircraftName = params.get('aircraftName');
            const processId = params.get('processId');
            const processName = params.get('processName');

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
        }

        if (path.startsWith('/tech-processes')) {
            const aircraftId = params.get('aircraftId');
            const aircraftName = params.get('aircraftName');
            const processId = params.get('processId');
            const processName = params.get('processName');
            const phaseId = params.get('phaseId');
            const phaseName = params.get('phaseName');

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
                    href: `/tech-processes?phaseId=${phaseId}&phaseName=${encodeURIComponent(phaseName)}&processId=${processId}&processName=${encodeURIComponent(processName)}&aircraftId=${aircraftId}&aircraftName=${encodeURIComponent(aircraftName)}`
                });
            }
        }

        if (path.startsWith('/details')) {
            const techProcId = params.get('techProcId');
            const techProcName = params.get('techProcName');
            const aircraftId = params.get('aircraftId');
            const aircraftName = params.get('aircraftName');
            const processId = params.get('processId');
            const processName = params.get('processName');
            const phaseId = params.get('phaseId');
            const phaseName = params.get('phaseName');

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
                    href: `/tech-processes?phaseId=${phaseId}&phaseName=${encodeURIComponent(phaseName)}&processId=${processId}&processName=${encodeURIComponent(processName)}&aircraftId=${aircraftId}&aircraftName=${encodeURIComponent(aircraftName)}`
                });
            }
            if (techProcId && techProcName) {
                breadcrumbs.push({
                    name: techProcName,
                    href: `/details?techProcId=${techProcId}&techProcName=${encodeURIComponent(techProcName)}&phaseId=${phaseId}&phaseName=${encodeURIComponent(phaseName)}&processId=${processId}&processName=${encodeURIComponent(processName)}&aircraftId=${aircraftId}&aircraftName=${encodeURIComponent(aircraftName)}`
                });
            }
        }

        const $breadcrumbs = $('#breadcrumbs');
        if ($breadcrumbs.length) {
            const html = breadcrumbs.map((item, index) => {
                if (index === breadcrumbs.length - 1) {
                    return `<span>${item.name}</span>`;
                } else {
                    return `<a href="${item.href}">${item.name}</a>`;
                }
            }).join(' > ');
            $breadcrumbs.html(html);
        }
    }
    */
    // Вызываем при загрузке страницы
    updateInterface();

    // Обработчик кликов по крошкам
    $('#breadcrumbs').on('click', 'a', function(e) {
        e.preventDefault();
        window.location.href = $(this).attr('href');
    });

    // Экспортируем функции, если нужно
    window.updateInterface = updateInterface;
    window.navigationState = navigationState;
});
