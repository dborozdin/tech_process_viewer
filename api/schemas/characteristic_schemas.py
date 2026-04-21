"""Characteristic / characteristic value schemas (Marshmallow + Smorest)."""

from marshmallow import Schema, EXCLUDE
from .common_schemas import fields


# ── Characteristic definitions ─────────────────────────────────────

class CharacteristicSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    sys_id = fields.Int(required=True, description="System ID of apl_characteristic")
    id = fields.Str(description="Designation/code")
    name = fields.Str(description="Display name")
    description = fields.Str(description="Optional description")


class CharacteristicListResponseSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    success = fields.Bool(dump_default=True)
    data = fields.List(fields.Nested(CharacteristicSchema),
                       description="List of characteristic definitions")


# ── Characteristic values ──────────────────────────────────────────

class CharacteristicValueSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    sys_id = fields.Int(required=True, description="System ID of value")
    characteristic_id = fields.Int(description="Linked characteristic sys_id")
    characteristic_name = fields.Str(description="Linked characteristic name")
    value = fields.Str(description="Display value")
    scope = fields.Str(description="PSS scope field")
    subtype = fields.Str(description="apl_*_characteristic_value subtype")
    unit = fields.Str(description="Unit name (if measured)")


class CharacteristicValueCreateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    item_id = fields.Int(required=True, description="Owner sys_id (PDF / BP / etc.)")
    characteristic_id = fields.Int(required=True, description="apl_characteristic sys_id")
    value = fields.Str(required=True, description="Value string")
    subtype = fields.Str(load_default="apl_descriptive_characteristic_value",
                         description="apl_*_characteristic_value subtype")
    item_type = fields.Str(load_default="apl_product_definition_formation",
                           description="Type of the owner item")


class CharacteristicValueUpdateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    value = fields.Str(required=True, description="New value string")
    subtype = fields.Str(load_default="apl_descriptive_characteristic_value")


class CharacteristicValueListResponseSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    success = fields.Bool(dump_default=True)
    data = fields.List(fields.Nested(CharacteristicValueSchema))


class CharacteristicValueResponseSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    success = fields.Bool(dump_default=True)
    message = fields.Str()
    data = fields.Dict(description="{sys_id: <int>}")
