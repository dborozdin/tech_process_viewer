# ILS Report Agent

## Назначение

AI-агент "автоматический генератор отчётов" для системы АЛП (Анализ Логистической Поддержки) на платформе ayatzk (PSS). Агент принимает вопрос пользователя на естественном языке, самостоятельно находит нужные сущности в БД, составляет запросы и возвращает ответ в виде HTML-отчёта.

## Домен

**ILS (Integrated Logistic Support)** — анализ логистической поддержки сложных машиностроительных изделий (самолёт, грузовик и т.п.):

- **Логистическая структура изделия** — древовидная декомпозиция изделия на элементы ИЛС (системы, подсистемы, компоненты) с классификацией LRU/SRU, показателями надёжности (MTBF/MTBUR), методами обслуживания
- **Регламентные работы** — технические операции обслуживания с периодичностью, ресурсами, трудоёмкостью
- **Анализ сценариев** — сценарии эксплуатации с профилями использования, распределением наработки
- **MSG-3** — структурированное планирование ТО по методологии MSG-3
- **Надёжность** — типы надёжности, показатели интенсивности отказов
- **Журнал эксплуатации** — для сериализованных изделий: наработка, отказы, инциденты
- **Инциденты** — записи об отказах и происшествиях с анализом причин

Часть объектов общая с PDM: папки, пользователи, организации, классификаторы.

## Техническая архитектура

### Стек
- **Backend**: Flask (Python), порт 5001
- **LLM**: OpenAI-совместимый API (OpenRouter/Groq/Ollama) с tool use
- **БД**: PSS REST API на порту 7239 (сервер приложений ayatzk)
- **Frontend**: Минимальный чат-интерфейс (HTML/JS)

### Структура
```
ILS/
├── app.py              # Flask-приложение
├── config.py           # Конфигурация LLM и PSS
├── agent/
│   ├── llm_client.py   # Обёртка OpenAI SDK
│   ├── tools.py        # JSON Schema определения tools
│   ├── tool_executor.py # Исполнение tools → PSS API
│   ├── orchestrator.py  # Agent loop
│   └── prompts.py      # System prompt, few-shot
├── pss/
│   ├── api_client.py   # Клиент PSS REST API
│   └── schema.py       # Парсинг словаря + HTML описаний
├── static/
│   └── index.html      # Чат UI
└── templates/
    └── report.html     # Шаблон HTML-отчётов
```

### PSS REST API (низкоуровневый)

Сервер: `http://localhost:7239/rest`

- `GET /rest/connect/{credentials}` — подключение, возвращает session_key
- `GET /rest/disconnect` — отключение (header X-APL-SessionKey)
- `POST /rest/query` — выполнение APL-запроса (body = текст запроса)
- `GET /rest&size=N&start=M/load/t=e&ent=TYPE&all_attrs=true` — загрузка экземпляров
- `POST /rest/save` — создание/обновление/удаление (JSON payload)

### APL Query синтаксис
```
SELECT NO_CASE Ext_ FROM Ext_{entity_type} END_SELECT
SELECT NO_CASE Ext_ FROM Ext_{entity_type(.field = "value")} END_SELECT
SELECT NO_CASE Ext_ FROM Ext_{entity_type(.# = #123)} END_SELECT
SELECT NO_CASE Ext_ FROM Ext_{entity_type(.ref_field->other_entity.field = "value")} END_SELECT
```

### БД для экспериментов
- База: `ils_lessons12`
- Пользователь: `Administrator` (без пароля)
- Credentials: `user=Administrator&db=ils_lessons12`

## Описание схемы данных

- **Словарь**: `../doc/apl_pss_a.dict` — определения сущностей и атрибутов
- **HTML-описания**: `../db_schema_doc/apl_pss_a_1419_data.htm` — описания на русском языке

### Ключевые ILS-сущности

| Категория | Сущности |
|-----------|----------|
| Логистическая структура | apl_ils_element, apl_ils_component, apl_ils_zone, apl_ils_zone_link |
| Сценарии | apl_ils_scenario, apl_ils_scenario_type, apl_ils_scenario_share |
| Техобслуживание | apl_ils_maintenance_task, apl_ils_resource |
| MSG-3 | apl_ils_msg3_function, apl_ils_msg3_application |
| Надёжность | apl_ils_reliability_type |
| Журнал эксплуатации | apl_logbook, apl_logbook_item |
| Инциденты | apl_incident, apl_incident_info, apl_incident_element, apl_crew |
| Запросы/Отчёты | ils_query, ils_query_parameter, ils_report |
| Общие (PDM+ILS) | organization, apl_folder, apl_classifier |

## Запуск

```bash
cd tech_process_viewer
pip install -r ILS/requirements.txt
python -m ILS.app
# Открыть http://localhost:5001/
```

## ОБЯЗАТЕЛЬНО: Тестирование изменений PSS API

При добавлении или изменении функций, работающих с PSS REST API (api/pss_*_api.py, ILS/pss/api_client.py):
1. Подключись к тестовой БД: `http://localhost:7239/rest`, БД `ils_lessons12`, пользователь `Administrator` (без пароля)
2. Вызови изменённую функцию и убедись, что она возвращает корректные данные (например, дерево логистической структуры не пустое, APL-запросы не возвращают ошибок)
3. Проверь граничные случаи: пустой результат, несуществующий компонент, большое дерево

Не отправляй изменения PSS API без ручной проверки на живой базе.

## Конфигурация LLM

В `config.py` или через переменные окружения:
- `LLM_BASE_URL` — URL API (OpenRouter, Groq, Ollama)
- `LLM_API_KEY` — API ключ
- `LLM_MODEL` — имя модели
