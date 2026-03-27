"""Фреймворк отчётов для PSS-aiR.

Отчёты — Jinja2-шаблоны в папке reports/ с метаданными в HTML-комментариях.
Заказчик добавляет новый отчёт, просто создав HTML-файл.
"""

import os
import re
from jinja2 import Environment, FileSystemLoader
from tech_process_viewer.globals import logger


REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'reports')


class ReportService:
    def __init__(self, db_api):
        self.db_api = db_api
        self.jinja_env = Environment(
            loader=FileSystemLoader(REPORTS_DIR),
            autoescape=True
        )

    def list_reports(self):
        """Список доступных отчётов (сканирует reports/).

        Парсит метаданные из HTML-комментариев:
            <!-- REPORT: Название -->
            <!-- DESCRIPTION: Описание -->
            <!-- PARAMS: param1 (type) - description -->

        Returns:
            list: [{name, title, description, params}]
        """
        reports = []
        if not os.path.isdir(REPORTS_DIR):
            return reports

        for fname in sorted(os.listdir(REPORTS_DIR)):
            if not fname.endswith('.html'):
                continue

            filepath = os.path.join(REPORTS_DIR, fname)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read(2000)  # Read only header
            except Exception:
                continue

            title = self._extract_comment(content, 'REPORT') or fname
            description = self._extract_comment(content, 'DESCRIPTION') or ''
            params_str = self._extract_comment(content, 'PARAMS') or ''

            reports.append({
                'name': fname.replace('.html', ''),
                'filename': fname,
                'title': title,
                'description': description,
                'params': params_str,
            })

        return reports

    def render_report(self, report_name, params):
        """Рендеринг отчёта.

        Args:
            report_name: Имя отчёта (без .html)
            params: dict с параметрами

        Returns:
            str: Отрендеренный HTML
        """
        filename = f"{report_name}.html"
        if not os.path.exists(os.path.join(REPORTS_DIR, filename)):
            return None

        # Get data for report
        context = self.get_report_data(report_name, params)

        template = self.jinja_env.get_template(filename)
        return template.render(**context)

    def get_report_data(self, report_name, params):
        """Диспетчер: загружает данные для конкретного отчёта.

        Для добавления нового отчёта с кастомными данными — добавьте
        elif report_name == 'my_report': и верните нужный dict.
        """
        if report_name == 'bom_report':
            return self._data_bom_report(params)
        elif report_name == 'process_report':
            return self._data_process_report(params)
        else:
            return params  # Pass params as-is for simple templates

    # Display name mappings for enum values (from db_schema_doc)
    FORMATION_TYPES = {
        'part': 'Деталь', 'assembly': 'Сборка', 'material': 'Материал',
        'kit': 'Комплект', 'komplex': 'Комплекс',
    }
    MAKE_OR_BUY = {
        'bought': 'Покупное', 'made': 'Изготовление', 'not_known': 'Не известно',
        'buy': 'Покупное', 'make': 'Изготовление', 'unknown': 'Не известно',
    }

    def _data_bom_report(self, params):
        """Данные для отчёта BOM."""
        product_id = params.get('product_id')
        if not product_id:
            return {'error': 'product_id required', 'product': {}, 'bom': []}

        from services.product_service import ProductService
        ps = ProductService(self.db_api)

        product = ps.get_product_details(int(product_id)) or {}
        bom = ps.export_bom_flat(int(product_id))

        return {
            'product': product, 'bom': bom,
            'formation_types': self.FORMATION_TYPES,
            'make_or_buy_types': self.MAKE_OR_BUY,
        }

    def _data_process_report(self, params):
        """Данные для отчёта по техпроцессам."""
        process_id = params.get('process_id')
        if not process_id:
            return {'error': 'process_id required', 'process': {}, 'hierarchy': []}

        from services.process_service import ProcessService
        ps = ProcessService(self.db_api)

        details = ps.get_process_details(int(process_id)) or {}
        return {'process': details}

    @staticmethod
    def _extract_comment(html_content, key):
        """Extract <!-- KEY: value --> from HTML."""
        pattern = rf'<!--\s*{key}:\s*(.+?)\s*-->'
        match = re.search(pattern, html_content, re.IGNORECASE)
        return match.group(1).strip() if match else None
