import logging
import os
import sys

logger = logging.getLogger("viewer")
logger.setLevel(logging.INFO)

# Папка для логов
logs_dir = os.path.join(os.path.abspath("."), "logs")
os.makedirs(logs_dir, exist_ok=True)

_log_path = os.path.join(logs_dir, "app.log")
_err_path = os.path.join(logs_dir, "errors.log")

mapping_names_table=None

if not logger.handlers:
    # Общий хэндлер для всех сообщений
    fh = logging.FileHandler(_log_path, encoding="utf-8", mode="w")
    fh.setLevel(logging.INFO)

    # Хэндлер только для ошибок
    eh = logging.FileHandler(_err_path, encoding="utf-8", mode="w")
    eh.setLevel(logging.ERROR)

    # Консольный вывод (не обязателен, но удобно)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    # Формат
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    fh.setFormatter(formatter)
    eh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # Добавляем хэндлеры
    logger.addHandler(fh)
    logger.addHandler(eh)
    logger.addHandler(ch)


# Функция для получения пути к ресурсам в собранном приложении
def resource_path(relative_path):
    """Возвращает абсолютный путь к ресурсу, учитывая _MEIPASS"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)
