# PSS-aiR CRUD UI — итоги фиксов и план по остаткам

**Стартовая точка**: 10/21 PASS (см. ранний прогон 2026-04-17 15:08–15:31).
**Текущий результат**: 14–16/21 PASS стабильно (best=16/21), нестабильно — 9/21 после неудачного restart_pss.
**Видео полного прохождения**: ещё не сохранено (нужно 100% PASS).
**Источники**: [test_results.html](test_results.html), [pss_crud.log](pss_crud.log), [_last_run.log](_last_run.log).

---

## ✅ Что починено

### 1. T08 — корневой баг `add_item_to_folder` (и каскад T09–T11, T13)
- **Что было**: второй `POST /api/crud/products` отвязывал первый продукт от папки.
- **Причина**: [api/pss_folders_api.py](api/pss_folders_api.py) `add_item_to_folder` записывал `folder.content = [новый-элемент]`, перезаписывая весь список содержимого.
- **Фикс**: сначала загружаем существующий `apl_folder.content`, добавляем новый элемент (с дедупликацией) и сохраняем целиком.
- **Эффект**: T08 стабильно PASS, разблокированы T09b, T10 (а также T11/T13/T16 после `force_folder_view`).

### 2. T14 — характеристики (item_type был захардкожен)
- **Что было**: `POST /api/crud/characteristics/values` HTTP 500 для PDF — `apl_descriptive_characteristic_value.item.type` всегда было `apl_business_process`.
- **Фикс в API** [api/pss_characteristic_api.py](api/pss_characteristic_api.py): добавлен параметр `item_type`, проброшен в payload PSS save. Раньше функция глотала ошибку и возвращала `None` — теперь пробрасывает наверх.
- **Фикс в route** [PSS-aiR/routes/crud.py](PSS-aiR/routes/crud.py): `item_type` принимается из request body.
- **Фикс в UI** [PSS-aiR/static/crud.js](PSS-aiR/static/crud.js) + [PSS-aiR/static/index.html](PSS-aiR/static/index.html): `addCharacteristic(itemId, itemType, …)` — PropertyPanel определяет тип по `currentItem.type` (`apl_business_process` для процессов, `apl_product_definition_formation` для изделий).
- **Фикс в `get_product_characteristics`** [api/pss_products_api.py](api/pss_products_api.py): теперь объединяет `apl_property_definition` и `apl_characteristic_value(.item = #pdf)` — только что созданные значения отображаются в PropertyPanel.
- **Эффект**: T14 PASS.

### 3. T16 — процессы и ресурсы (folder_id не принимался; `isProcess` не распознавал `apl_business_process`)
- **Фикс в `create_process`** [PSS-aiR/routes/crud.py](PSS-aiR/routes/crud.py): принимает `folder_id`, после создания BP вызывает `folders_api.add_item_to_folder(bp_sys_id, 'apl_business_process', folder_id)` — TPROC появляется в Aircrafts.
- **Фикс UI** [PSS-aiR/static/crud.js](PSS-aiR/static/crud.js) + [PSS-aiR/static/index.html](PSS-aiR/static/index.html): `createProcess(folderId, …)` теперь шлёт `folder_id` из текущей папки; кнопка `+ Процесс` передаёт `folderId`.
- **Фикс PropertyPanel** [PSS-aiR/static/index.html:2459](PSS-aiR/static/index.html#L2459): `isProcess` распознаёт `apl_business_process` — у процесса появляется вкладка «Ресурсы».
- **Фикс `create_resource`** [api/pss_resources_api.py](api/pss_resources_api.py): payload больше не отправляет `unit_component`/`object` со ссылкой на `id=0` — PSS отвергал такой save c HTTP 500.
- **Эффект**: T16 PASS.

### 4. Поиск изделий (T09 — добавление в BOM)
- **Что было**: APL `LIKE "*текст*"` не поддерживается этой версией PSS — `search_products` возвращал `[]`, в BOM-modal «Ничего не найдено».
- **Фикс** [api/pss_products_api.py](api/pss_products_api.py) `search_products`: убраны `*`-wildcards (используется bare LIKE), поиск идёт и по `product`, и по `apl_product_definition_formation`, по `id` и `name`. Для кириллицы — fallback на загрузку всех записей и фильтрацию в Python (LIKE с кириллицей в APL сломан, см. [CLAUDE.md](../CLAUDE.md)).
- **Эффект**: search возвращает результаты, T09 уже не валится на «search empty» (но см. ниже про BOM-tree refresh).

### 5. Поиск документов (T18) — расширен фильтр
- [PSS-aiR/routes/crud.py](PSS-aiR/routes/crud.py) `search_documents`: ищет и по `id`, и по `name`; для кириллицы — в Python.

### 6. UI race в `loadFolderContents` (помогает T08-каскаду)
- [PSS-aiR/static/index.html](PSS-aiR/static/index.html): добавлен generation-counter — устаревший fetch не перезаписывает результат свежего.

### 7. Доступ из Playwright к `bus`/`contentView`/`propertyPanel`
- [PSS-aiR/static/index.html](PSS-aiR/static/index.html): после инициализации компоненты выставляются на `window.*`. Это позволяет тесту через `page.evaluate` принудительно вернуть ContentView в folder-view (`force_folder_view` в [PSS-aiR/test_ui_scenarios.py](PSS-aiR/test_ui_scenarios.py)) после операций в BOM-режиме — раньше T12/T13/T16 падали потому что после T09b/T10/T11 view оставался `bom`.

### 8. Инфраструктура отчёта и теста
- HTML-отчёт: добавлены колонки **Окончание** и **Длит., мс**; для FAIL — раскрываемый `<details>` со stack-trace.
- `run()`: state (R/times/end_times/errors) externalized как параметры — partial state выживает даже unhandled exception в любом сценарии.
- `restart_pss()`: timeout PowerShell `Stop-Process` поднят с 10 → 60 сек (раньше R#3+ обрывались).
- `sel_folder()`: убраны невалидные `timeout=N` у `count()`/`is_visible()`/`text_content()` — раньше тихо проглатывались общим `except`, и папка «не находилась».
- UTF-8 stdout: `sys.stdout.reconfigure('utf-8')` — debug-print с emoji (📦) больше не убивают тест на Windows cp1251.
- Отдельный баг-фикс `pss_docs_api._upload_blob`: возврат при ошибке заменён с tuple `(response.status_code, …)` на `None` (раньше: `NameError: name 'response' is not defined`, теперь: чистый 500 «Не удалось создать документ»).

---

## ❌ Остаются — реальные баги бэкенда/PSS, требуют отдельной работы

| # | Тест | Симптом | Где копать | Сложность |
|---|------|---------|------------|-----------|
| 1 | T09 «BOM — добавить компонент» | API `POST /products/{id}/bom` → HTTP 201, но в `#contentArea` BOM-tree не появляется новая строка даже через ~12 сек ретраев | `loadProductBOM` в [PSS-aiR/static/index.html](PSS-aiR/static/index.html) — после `addBomComponent` callback не дотягивает свежий BOM. Скорее всего `services/product_service.get_product_bom` использует старый снимок (PSS read-after-write race). Нужен явный re-fetch после save с задержкой ≥3 сек или query-инвалидация. | Средняя |
| 2 | T11 «BOM — удалить связь» | После `crud-bom-delete` строка остаётся видна | Тот же путь: `delete_bom_link` → reload → видит старое. Аналогичный фикс с T09. | Средняя (каскад от T09) |
| 3 | T15 «Удаление характеристики» | `DELETE /characteristics/values/{id}` → HTTP 200 success, но в panel значение остаётся | `delete_instance(sys_id, 'apl_characteristic_value')` в [api/pss_api.py:413](api/pss_api.py#L413) шлёт `{id, type:null}`. Возможно PSS требует **конкретный subtype** (apl_descriptive_…), а не супертип — тогда save проходит «впустую». Нужно либо передавать subtype из ответа `_displayChars`, либо после delete делать GET single и сверять `count_all == 0`. | Средняя |
| 4 | T17 «Удаление ресурса» | Аналогично T15 — DELETE 200, но строка остаётся | Тот же `delete_instance` для `apl_business_process_resource` — требуется конкретный subtype или verify-after-delete. | Средняя |
| 5 | T18 «Привязка документа» | Search документов возвращает `[]`, потому что в БД `apl_document` пуст и `upload_blob` не работает (PSS REST `URL_UPLOAD` не отвечает 200) | `pss_docs_api.upload_blob` шлёт multipart на `URL_UPLOAD`, PSS не отвечает 200. Либо неверный URL/headers, либо PSS-Lite не поддерживает blob upload в этом билде. Альтернатива: сделать endpoint, создающий **только метаданные** `apl_document` без `apl_digital_document` для тестовых сценариев. | Высокая (PSS infra) |
| 6 | T19 «Отвязка документа» | Каскад от T18 — нечего отвязывать | Зависит от T18. | Низкая (после T18) |

---

## Сводка изменений

| Файл | Что | Тесты, которые позеленели |
|------|-----|--------------------------|
| [api/pss_folders_api.py](api/pss_folders_api.py) | `add_item_to_folder` сохраняет существующий content | T08, T09b, T10 + разблокировано все остальное в Aircrafts |
| [api/pss_characteristic_api.py](api/pss_characteristic_api.py) | `item_type` параметр, проброс ошибки | T14 |
| [api/pss_products_api.py](api/pss_products_api.py) | `search_products` без `*`-wildcards; `get_product_characteristics` объединяет definitions+values | T09 (search), T14 (отображение) |
| [api/pss_resources_api.py](api/pss_resources_api.py) | не отправляет `unit_component`/`object` с id=0 | T16 |
| [api/pss_docs_api.py](api/pss_docs_api.py) | `upload_blob` возвращает None вместо tuple с PreparedRequest | T18 (теперь не падает с NameError, но видим реальную причину) |
| [PSS-aiR/routes/crud.py](PSS-aiR/routes/crud.py) | `create_process` принимает `folder_id`; `create_characteristic_value` пробрасывает `item_type`; `search_documents` ищет по name+id | T16, T14 |
| [PSS-aiR/static/index.html](PSS-aiR/static/index.html) | `isProcess` распознаёт `apl_business_process`; `_renderDocuments` сохраняет toolbar при ошибке fetch; race-guard в `loadFolderContents`; `window.bus`/`contentView`/`propertyPanel` экспортированы | T16, T18 (attach button), T13/T08 |
| [PSS-aiR/static/crud.js](PSS-aiR/static/crud.js) | `createProcess(folderId, …)`; `addCharacteristic(itemId, itemType, …)` | T12/T16, T14 |
| [PSS-aiR/test_ui_scenarios.py](PSS-aiR/test_ui_scenarios.py) | `force_folder_view` helper; sel_folder без невалидных timeout; UTF-8 stdout; raised PowerShell timeout; T08 с API-подтверждением между creates; hardening waits для T04/T09/T12/T13/T14/T16 | устойчивость |

---

## Финальная рекомендация

Чтобы добиться **21/21** и сохранить видео:

1. **Высокий приоритет** — починить `delete_instance` так, чтобы PSS реально удалял запись (T15, T17). Самое простое — после успешного `delete_instance` сделать GET single и убедиться что запись исчезла; иначе попробовать с конкретным subtype.
2. **Средний приоритет** — после `POST /products/{id}/bom` форсировать re-fetch BOM-tree с явной паузой 3-5 сек, либо добавить query-инвалидацию на стороне UI (T09 → T11).
3. **Низкий приоритет / отдельный спринт** — починить blob upload в PSS REST либо ввести альтернативный endpoint создания `apl_document` без файла (T18 → T19).

Все три категории — точечные, не требуют реструктуризации.
