# Tech Process Viewer

Web-приложение на Flask для работы с данными PSS (Product Structure System).

## Состав проекта

Приложение включает три части, доступные после запуска:

1. **Просмотрщик техпроцессов** — [http://localhost:5000/](http://localhost:5000/)
   Навигация по изделиям, бизнес-процессам, фазам, техпроцессам и операциям.

2. **Entity Viewer** — [http://localhost:5000/entity-viewer](http://localhost:5000/entity-viewer)
   Универсальный браузер сущностей БД: просмотр типов, экземпляров, создание/редактирование/удаление.

3. **Документация API (OpenAPI)** — [http://localhost:5000/api/docs](http://localhost:5000/api/docs)
   Интерактивная документация Swagger UI. Также доступен ReDoc: [http://localhost:5000/api/redoc](http://localhost:5000/api/redoc).

## Предварительные требования

- Python 3.10+
- **Сервер приложений PSS** с REST API (по умолчанию `http://localhost:7239`).
  Без запущенного сервера PSS приложение запустится, но все функции, связанные с данными, будут недоступны — подключение к БД невозможно.

## Развертывание и запуск

1. Клонировать репозиторий:
   ```bash
   git clone https://github.com/dborozdin/tech_process_viewer.git
   cd tech_process_viewer
   ```

2. Создать виртуальное окружение и активировать его:
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # Linux/macOS
   source .venv/bin/activate
   ```

3. Установить зависимости:
   ```bash
   pip install -r requirements.txt
   ```

4. Убедиться, что сервер приложений PSS запущен и доступен (по умолчанию `http://localhost:7239`).

5. Запустить приложение:
   ```bash
   flask --app app:app run
   ```
   Или через VS Code — конфигурация отладки **"Flask App (Debug)"** (F5).

6. Открыть в браузере: [http://localhost:5000/](http://localhost:5000/)

## Конфигурация

Настройки подключения к БД находятся в `config.py`:

| Параметр | Значение по умолчанию | Описание |
|---|---|---|
| `DEFAULT_DB_SERVER` | `http://localhost:7239` | Адрес сервера PSS |
| `DEFAULT_DB_NAME` | `pss_moma_08_07_2025` | Имя базы данных |
| `DEFAULT_DB_USER` | `Administrator` | Пользователь |
