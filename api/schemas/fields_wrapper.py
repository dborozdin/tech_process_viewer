"""
Wrapper для полей marshmallow, добавляющий поддержку параметра description.
"""

from marshmallow import fields as ma_fields


class FieldWrapper:
    """Wrapper класс для создания полей с поддержкой description"""

    def __init__(self, field_class):
        self.field_class = field_class

    def __call__(self, *args, description=None, **kwargs):
        """Перехватываем description и добавляем в metadata"""
        if description is not None:
            if 'metadata' not in kwargs:
                kwargs['metadata'] = {}
            kwargs['metadata']['description'] = description
        return self.field_class(*args, **kwargs)


# Создаем обертки для всех часто используемых полей
Str = FieldWrapper(ma_fields.Str)
Int = FieldWrapper(ma_fields.Int)
Bool = FieldWrapper(ma_fields.Bool)
Float = FieldWrapper(ma_fields.Float)
Dict = FieldWrapper(ma_fields.Dict)
List = FieldWrapper(ma_fields.List)
Nested = FieldWrapper(ma_fields.Nested)
Raw = FieldWrapper(ma_fields.Raw)

# Экспортируем все wrapped поля
__all__ = ['Str', 'Int', 'Bool', 'Float', 'Dict', 'List', 'Nested', 'Raw']
