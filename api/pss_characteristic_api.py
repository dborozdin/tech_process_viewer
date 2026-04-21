"""API для работы с характеристиками (apl_characteristic) и их значениями (apl_characteristic_value).

apl_characteristic — тип/определение характеристики (название, единица измерения).
apl_characteristic_value — супертип значения, привязанного к объекту через .item (select).
    Подтипы: apl_descriptive_characteristic_value, apl_measured_characteristic_value,
             apl_enumeration_characteristic_value, apl_boolean_characteristic_value,
             apl_reference_value, apl_monetary_characteristic_value,
             apl_aggregation_characteristic_value, apl_point_in_time_characteristic_value,
             apl_table_characteristic_value.
    Поле scope (label) содержит отображаемое значение независимо от подтипа.
"""

from tech_process_viewer.globals import logger


class CharacteristicAPI:
    def __init__(self, db_api):
        self.db_api = db_api

    # ── Типы характеристик (apl_characteristic) ──────────────────────

    def list_characteristics(self, limit=500):
        """Получить список всех определений характеристик.

        Returns:
            list: [{id, type, attributes: {id, name, description, unit, code, ...}}]
        """
        query = """SELECT NO_CASE
        Ext_
        FROM
        Ext_{apl_characteristic}
        END_SELECT"""
        result = self.db_api.query_apl(query)
        instances = result.get('instances', []) if result else []
        return instances[:limit]

    def get_characteristic(self, char_sys_id):
        """Получить определение характеристики по sys_id.

        Returns:
            dict or None: {id, type, attributes: {id, name, description, unit, ...}}
        """
        query = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{#{char_sys_id}}}
        END_SELECT"""
        result = self.db_api.query_apl(query)
        instances = result.get('instances', []) if result else []
        return instances[0] if instances else None

    def find_characteristic_by_name(self, name):
        """Найти характеристику по имени.

        Returns:
            dict or None
        """
        query = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{apl_characteristic(.name = "{name}")}}
        END_SELECT"""
        result = self.db_api.query_apl(query)
        instances = result.get('instances', []) if result else []
        return instances[0] if instances else None

    # ── Значения характеристик (apl_characteristic_value) ────────────

    def get_values_for_item(self, item_sys_id):
        """Получить ВСЕ значения характеристик для объекта.

        apl_characteristic_value.item — тип select, запрос по одному item работает.
        Возвращаемые экземпляры будут конкретных подтипов
        (apl_descriptive_characteristic_value и т.д.).

        Args:
            item_sys_id: sys_id объекта (бизнес-процесс, изделие и т.д.)

        Returns:
            list: [{id, type, attributes: {characteristic, scope, ...}}]
        """
        query = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{apl_characteristic_value(.item = #{item_sys_id})}}
        END_SELECT"""
        try:
            result = self.db_api.query_apl(query)
            return result.get('instances', []) if result else []
        except Exception as e:
            logger.error(f"Error getting characteristic values for item #{item_sys_id}: {e}")
            return []

    def get_values_for_items_batch(self, item_sys_ids):
        """Получить значения характеристик для нескольких объектов.

        Поскольку .item — тип select и IN на нём может не работать,
        выполняем запрос по каждому item отдельно и группируем результат.

        Args:
            item_sys_ids: list of sys_id объектов

        Returns:
            dict: {item_sys_id_str: [instance, ...]}
        """
        grouped = {}
        for item_id in item_sys_ids:
            values = self.get_values_for_item(item_id)
            if values:
                grouped[str(item_id)] = values
        return grouped

    def get_values_for_items_by_characteristic(self, item_sys_ids, char_sys_id):
        """Получить значения конкретной характеристики для нескольких объектов.

        Для apl_reference_value: scope часто пуст, значение берётся из val
        (ссылка на объект, например apl_classifier_level) через batch-резолв.

        Args:
            item_sys_ids: list of sys_id объектов
            char_sys_id: sys_id характеристики (apl_characteristic)

        Returns:
            dict: {item_sys_id_str: [{value, scope, subtype}]}
        """
        grouped = {}
        ref_ids_to_resolve = []  # (item_id_str, value_index, ref_id)

        for item_id in item_sys_ids:
            query = f"""SELECT NO_CASE
            Ext_
            FROM
            Ext_{{apl_characteristic_value(.item = #{item_id} AND .characteristic = #{char_sys_id})}}
            END_SELECT"""
            try:
                result = self.db_api.query_apl(query)
                instances = result.get('instances', []) if result else []
                if instances:
                    values = []
                    for inst in instances:
                        parsed = self._extract_display_value(inst)
                        if not parsed['value'] and '_ref_id' in parsed:
                            ref_ids_to_resolve.append(
                                (str(item_id), len(values), parsed['_ref_id'])
                            )
                        values.append(parsed)
                    grouped[str(item_id)] = values
            except Exception as e:
                logger.error(
                    f"Error getting char #{char_sys_id} for item #{item_id}: {e}"
                )

        # Batch-резолв ссылочных значений (apl_reference_value → val.name)
        if ref_ids_to_resolve:
            unique_ids = list(set(r[2] for r in ref_ids_to_resolve))
            ref_map = {}
            try:
                ids_str = ", ".join(f"#{rid}" for rid in unique_ids)
                query = f"SELECT NO_CASE Ext_ FROM Ext_{{{ids_str}}} END_SELECT"
                result = self.db_api.query_apl(query)
                if result:
                    for inst in result.get('instances', []):
                        attrs = inst.get('attributes', {})
                        ref_map[inst['id']] = attrs.get('name', attrs.get('id', ''))
            except Exception as e:
                logger.error(f"Error resolving reference values: {e}")

            for item_id_str, idx, ref_id in ref_ids_to_resolve:
                name = ref_map.get(ref_id, '')
                if name and item_id_str in grouped and idx < len(grouped[item_id_str]):
                    grouped[item_id_str][idx]['value'] = str(name)

        return grouped

    def _extract_display_value(self, instance):
        """Извлечь отображаемое значение из экземпляра apl_characteristic_value.

        Использует scope (label) как основное отображаемое значение.
        Для apl_reference_value: scope часто пуст, значение в val (ссылка).
        Ссылочные значения помечаются _ref_id для batch-резолва.

        Returns:
            dict: {value, scope, subtype, unit?, _ref_id?}
        """
        attrs = instance.get('attributes', {})
        subtype = instance.get('type', 'apl_characteristic_value')
        scope = attrs.get('scope', '')

        # Типизированное значение зависит от подтипа
        typed_value = None
        ref_id = None
        if subtype in ('apl_descriptive_characteristic_value',
                       'apl_enumeration_characteristic_value'):
            typed_value = attrs.get('val', '')
        elif subtype in ('apl_measured_characteristic_value',
                         'apl_monetary_characteristic_value',
                         'apl_aggregation_characteristic_value'):
            typed_value = attrs.get('val')
        elif subtype == 'apl_boolean_characteristic_value':
            typed_value = attrs.get('value')
        elif subtype in ('apl_reference_value', 'apl_reference_value_version'):
            # val — ссылка на объект, нужен batch-резолв для name
            val_ref = attrs.get('val', {})
            if isinstance(val_ref, dict) and 'id' in val_ref:
                ref_id = val_ref['id']

        # unit может быть и на уровне characteristic_value, и на уровне characteristic
        unit_ref = attrs.get('unit', {})
        unit_name = ''
        if isinstance(unit_ref, dict):
            unit_name = unit_ref.get('name', '')

        display = str(scope) if scope else (str(typed_value) if typed_value is not None else '')

        result = {
            'value': display,
            'scope': str(scope) if scope else '',
            'typed_value': typed_value,
            'subtype': subtype,
            'unit': unit_name,
        }
        if ref_id:
            result['_ref_id'] = ref_id
        return result

    # ── Создание / обновление / удаление значений характеристик ───────

    def create_characteristic_value(self, item_sys_id, char_sys_id, value,
                                    subtype='apl_descriptive_characteristic_value',
                                    item_type='apl_product_definition_formation'):
        """Создать значение характеристики для объекта.

        Args:
            item_sys_id: sys_id объекта (бизнес-процесс, изделие и т.д.)
            char_sys_id: sys_id определения характеристики (apl_characteristic)
            value: значение (строка или число)
            subtype: подтип значения характеристики
            item_type: тип объекта-владельца (apl_product_definition_formation,
                apl_business_process и т.д.)

        Returns:
            dict: созданный экземпляр

        Raises:
            Exception: если PSS вернул ошибку — пробрасывается наверх с понятным
                сообщением, чтобы route мог показать пользователю.
        """
        attributes = {
            'item': {'id': int(item_sys_id), 'type': item_type},
            'characteristic': {'id': int(char_sys_id), 'type': 'apl_characteristic'},
            'scope': str(value),
        }

        # Для разных подтипов устанавливаем val по-разному
        if subtype in ('apl_descriptive_characteristic_value',
                       'apl_enumeration_characteristic_value'):
            attributes['val'] = str(value)
        elif subtype in ('apl_measured_characteristic_value',
                         'apl_monetary_characteristic_value'):
            try:
                attributes['val'] = float(value)
            except (ValueError, TypeError):
                attributes['val'] = 0
        elif subtype == 'apl_boolean_characteristic_value':
            attributes['value'] = str(value).lower() in ('true', '1', 'yes', 'да')

        result = self.db_api.create_instance(subtype, attributes)
        logger.info(f"Created characteristic value for item #{item_sys_id} ({item_type}), char #{char_sys_id}, subtype={subtype}")
        return result

    def update_characteristic_value(self, value_sys_id, new_value, subtype='apl_descriptive_characteristic_value'):
        """Обновить значение характеристики.

        Args:
            value_sys_id: sys_id экземпляра значения
            new_value: новое значение
            subtype: подтип (для правильного маппинга атрибутов)

        Returns:
            bool: True если успешно
        """
        updates = {'scope': str(new_value)}

        if subtype in ('apl_descriptive_characteristic_value',
                       'apl_enumeration_characteristic_value'):
            updates['val'] = str(new_value)
        elif subtype in ('apl_measured_characteristic_value',
                         'apl_monetary_characteristic_value'):
            try:
                updates['val'] = float(new_value)
            except (ValueError, TypeError):
                updates['val'] = 0
        elif subtype == 'apl_boolean_characteristic_value':
            updates['value'] = str(new_value).lower() in ('true', '1', 'yes', 'да')

        try:
            result = self.db_api.update_instance(value_sys_id, subtype, updates)
            if result:
                logger.info(f"Updated characteristic value #{value_sys_id}")
            return result
        except Exception as e:
            logger.error(f"Error updating characteristic value #{value_sys_id}: {e}")
            return False

    def delete_characteristic_value(self, value_sys_id):
        """Удалить значение характеристики.

        Args:
            value_sys_id: sys_id экземпляра значения

        Returns:
            bool: True если успешно
        """
        try:
            result = self.db_api.delete_instance(value_sys_id, 'apl_characteristic_value')
            if result:
                logger.info(f"Deleted characteristic value #{value_sys_id}")
            return result
        except Exception as e:
            logger.error(f"Error deleting characteristic value #{value_sys_id}: {e}")
            return False

    # ── Значения через версии (apl_characteristic_value_version) ─────

    def get_values_via_version(self, bp_version_sys_id):
        """Получить значения характеристик через версию бизнес-процесса.

        apl_business_process_version.characteristic_value_versions — агрегированный список.
        apl_characteristic_value_version.item — типизированная ссылка (instance 867),
        поддерживает IN.

        Args:
            bp_version_sys_id: sys_id версии бизнес-процесса

        Returns:
            list: [{id, type, attributes: {characteristic, scope, ...}}]
        """
        query = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{apl_characteristic_value_version(.item = #{bp_version_sys_id})}}
        END_SELECT"""
        try:
            result = self.db_api.query_apl(query)
            return result.get('instances', []) if result else []
        except Exception as e:
            logger.error(
                f"Error getting char value versions for BP version #{bp_version_sys_id}: {e}"
            )
            return []

    def get_values_via_versions_batch(self, bp_version_sys_ids):
        """Batch-запрос значений характеристик через версии БП.

        apl_characteristic_value_version.item — типизированная ссылка, IN работает.

        Args:
            bp_version_sys_ids: list of sys_id версий

        Returns:
            dict: {version_sys_id_str: [instance, ...]}
        """
        if not bp_version_sys_ids:
            return {}

        ids_str = ", ".join(f"#{vid}" for vid in bp_version_sys_ids)
        query = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{apl_characteristic_value_version(.item IN ({ids_str}))}}
        END_SELECT"""
        try:
            result = self.db_api.query_apl(query)
            instances = result.get('instances', []) if result else []
        except Exception as e:
            logger.error(f"Error batch getting char value versions: {e}")
            return {}

        grouped = {}
        for inst in instances:
            attrs = inst.get('attributes', {})
            item_ref = attrs.get('item', {})
            item_id = item_ref.get('id') if isinstance(item_ref, dict) else None
            if item_id:
                grouped.setdefault(str(item_id), []).append(inst)
        return grouped
