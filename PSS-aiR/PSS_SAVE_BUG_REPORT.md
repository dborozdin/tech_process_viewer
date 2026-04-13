# Bug Report: POST /rest/save returns APLAPIERR_FILE_IO

## Summary

POST /rest/save на сервере PSS (AplNetTransportServTCP.exe, версия из PSS_MUI) зависает на ~67 секунд и возвращает HTTP 500 с ошибкой `APLAPIERR_FILE_IO` для любой операции записи.

Чтение (GET /rest/connect, POST /rest/query) работает стабильно.

## Environment

- **PSS Server**: `C:\Program Files (x86)\PSS_MUI\AplNetTransportServTCP.exe`
- **Version**: PSS Lite Server (v5) unicode, FileVersion 0.0.2.0, ProductVersion 5.0.0.0
- **Product**: PDM STEP Suite, CALS Centre "Applied Logistic"
- **File date**: 10.04.2026, Size: 1,496,064 bytes
- **Port**: 7239 (`/p:7239`)
- **Database**: `pss_moma_08_07_2025` (file-based, `.aplb`, ~150 MB)
- **Database path**: `c:\_pss_lite_db\pss_moma_08_07_2025.aplb`
- **OS**: Windows 11 Enterprise LTSC 2024 (10.0.26100)
- **User**: Administrator (без пароля)

## Steps to Reproduce

### 1. Подготовка БД

```powershell
# Остановить PSS-сервер (если запущен)
Get-Process | Where-Object { $_.Path -like '*AplNetTransportServ*' } | Stop-Process -Force

# Восстановить БД из бэкапа
Copy-Item "c:\_pss_lite_db\pss_moma_08_07_2025_copy.aplb" "c:\_pss_lite_db\pss_moma_08_07_2025.aplb" -Force

# Удалить вспомогательные файлы
Remove-Item "c:\_pss_lite_db\pss_moma_08_07_2025.aplb.*" -ErrorAction SilentlyContinue
Remove-Item "c:\_pss_lite_db\pss_moma_08_07_2025.aclst*" -ErrorAction SilentlyContinue
Remove-Item "c:\_pss_lite_db\pss_moma_08_07_2025.crc*" -ErrorAction SilentlyContinue
Remove-Item "c:\_pss_lite_db\pss_moma_08_07_2025.bak*" -ErrorAction SilentlyContinue
Remove-Item "c:\_pss_lite_db\pss_moma_08_07_2025.tmp*" -ErrorAction SilentlyContinue
```

### 2. Запуск сервера

```powershell
Start-Process "C:\Program Files (x86)\PSS_MUI\AplNetTransportServTCP.exe" -ArgumentList "/p:7239"
```

### 3. Подключение (работает)

```bash
curl http://localhost:7239/rest/connect/user=Administrator&db=pss_moma_08_07_2025
```

**Результат**: HTTP 200, возвращает `session_key`

### 4. Чтение (работает)

```bash
curl -X POST http://localhost:7239/rest/query \
  -H "X-APL-SessionKey: <session_key>" \
  -d 'SELECT Ext_ FROM Ext_{apl_folder} END_SELECT'
```

**Результат**: HTTP 200, 81 папка, ~2 сек

### 5. Запись (ОШИБКА)

```bash
curl -X POST http://localhost:7239/rest/save \
  -H "X-APL-SessionKey: <session_key>" \
  -H "Content-Type: application/json" \
  -d '{
    "format": "apl_json_1",
    "dictionary": "apl_pss_a",
    "instances": [{
      "id": 0,
      "index": 0,
      "type": "apl_product_definition_formation",
      "attributes": {
        "formation_type": "1",
        "make_or_buy": "1",
        "of_product": {
          "id": 0,
          "index": 1,
          "type": "product",
          "attributes": {
            "id": "TEST-001",
            "name": "TestProduct"
          }
        }
      }
    }]
  }'
```

**Результат**:
- Запрос зависает на **~67 секунд**
- HTTP **500**
- Тело ответа:

```json
{
  "_processingTime": "00:01:04.891",
  "error_description": [
    "Throw: APLAPIERR_FILE_IO ( Ошибка чтения или записи файла )"
  ],
  "_processingStart": "11.04.2026 13:33:18.907"
}
```

## Expected Behavior

POST /rest/save должен создать объект и вернуть HTTP 200 с `instances` содержащими новый id.

## Actual Behavior

- Save зависает на ~67 секунд
- Возвращает HTTP 500 APLAPIERR_FILE_IO
- Сессия аннулируется после ошибки
- Повторяется стабильно для любого типа save (create, update, delete)

## Additional Notes

- **Формат JSON payload** — проверен, соответствует формату из `pss_products_api.py` и `pss_bp_api.py`
- **Ранее**: аналогичный сервер из `C:\Program Files (x86)\ILS_Suite\AplNetTransportServTCP.exe` (старая версия) выполнял save-операции стабильно (490/490 PASS в стресс-тесте)
- **Тест**: автоматический стресс-тест — `python PSS-aiR/test_pss_stress_log.py`, лог: `PSS-aiR/stress_test_log.txt`

## Reproduction Logs

Полный лог запросов/ответов: [`PSS-aiR/stress_test_log.txt`](stress_test_log.txt)
