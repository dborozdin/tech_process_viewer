"""Characteristics API routes (Smorest, /api/v1/characteristics).

Migrated from api/routes/crud_routes.py — exposes definitions list and CRUD
on apl_characteristic_value via flask-smorest with Marshmallow validation.
"""

from flask.views import MethodView
from flask_smorest import Blueprint, abort

from ..schemas.characteristic_schemas import (
    CharacteristicListResponseSchema,
    CharacteristicValueListResponseSchema,
    CharacteristicValueCreateSchema,
    CharacteristicValueUpdateSchema,
    CharacteristicValueResponseSchema,
)
from ..schemas.common_schemas import ErrorSchema, SuccessResponseSchema


blp = Blueprint(
    "characteristics",
    __name__,
    url_prefix="/api/v1/characteristics",
    description="Characteristic definitions and per-item values",
)


def _api():
    from tech_process_viewer.api.app_helpers import get_api
    api = get_api()
    if api is None or api.connect_data is None:
        abort(401, message="Not connected to database. POST /api/connect first.")
    return api


@blp.route("/")
class CharacteristicList(MethodView):
    @blp.response(200, CharacteristicListResponseSchema)
    @blp.alt_response(401, schema=ErrorSchema, description="Not connected")
    @blp.doc(description="List all apl_characteristic definitions")
    def get(self):
        api = _api()
        chars = api.characteristic_api.list_characteristics()
        result = []
        for ch in chars:
            attrs = ch.get("attributes", {}) or {}
            result.append({
                "sys_id": ch.get("id"),
                "id": attrs.get("id", ""),
                "name": attrs.get("name", ""),
                "description": attrs.get("description", ""),
            })
        return {"success": True, "data": result}


@blp.route("/values/<int:item_id>")
class CharacteristicValuesForItem(MethodView):
    @blp.response(200, CharacteristicValueListResponseSchema)
    @blp.alt_response(401, schema=ErrorSchema, description="Not connected")
    @blp.doc(description="Get all characteristic values attached to an item (PDF / BP / ...)")
    def get(self, item_id):
        api = _api()
        values = api.characteristic_api.get_values_for_item(item_id)
        result = []
        for val in values:
            attrs = val.get("attributes", {}) or {}
            char_ref = attrs.get("characteristic", {})
            char_name = ""
            char_id = None
            if isinstance(char_ref, dict) and "id" in char_ref:
                char_id = char_ref["id"]
                ci = api.characteristic_api.get_characteristic(char_id)
                if ci:
                    char_name = ci.get("attributes", {}).get("name", "")
            parsed = api.characteristic_api._extract_display_value(val)
            result.append({
                "sys_id": val.get("id"),
                "characteristic_id": char_id,
                "characteristic_name": char_name,
                "value": parsed.get("value", ""),
                "scope": parsed.get("scope", ""),
                "subtype": val.get("type", ""),
                "unit": parsed.get("unit", ""),
            })
        return {"success": True, "data": result}


@blp.route("/values")
class CharacteristicValueCreate(MethodView):
    @blp.arguments(CharacteristicValueCreateSchema)
    @blp.response(201, CharacteristicValueResponseSchema)
    @blp.alt_response(400, schema=ErrorSchema, description="Validation failed")
    @blp.alt_response(401, schema=ErrorSchema, description="Not connected")
    @blp.alt_response(500, schema=ErrorSchema, description="PSS save failed")
    @blp.doc(description="Create a new apl_*_characteristic_value linked to an item")
    def post(self, data):
        api = _api()
        try:
            result = api.characteristic_api.create_characteristic_value(
                data["item_id"], data["characteristic_id"],
                data["value"], data["subtype"]
            )
            if not result:
                abort(500, message="Failed to create characteristic value (PSS returned no instance)")
            sys_id = result.get("id") if isinstance(result, dict) else result
            return {"success": True, "message": "Characteristic value created",
                    "data": {"sys_id": sys_id}}
        except Exception as e:
            abort(500, message=str(e))


@blp.route("/values/<int:value_id>")
class CharacteristicValueDetail(MethodView):
    @blp.arguments(CharacteristicValueUpdateSchema)
    @blp.response(200, SuccessResponseSchema)
    @blp.alt_response(401, schema=ErrorSchema, description="Not connected")
    @blp.alt_response(500, schema=ErrorSchema)
    @blp.doc(description="Update value (re-saves apl_*_characteristic_value with new scope/val)")
    def put(self, data, value_id):
        api = _api()
        try:
            ok = api.characteristic_api.update_characteristic_value(
                value_id, data["value"], data["subtype"]
            )
            if not ok:
                abort(500, message="PSS save returned no instance")
            return {"success": True, "message": "Characteristic value updated"}
        except Exception as e:
            abort(500, message=str(e))

    @blp.response(200, SuccessResponseSchema)
    @blp.alt_response(401, schema=ErrorSchema, description="Not connected")
    @blp.alt_response(500, schema=ErrorSchema)
    @blp.doc(description="Delete characteristic value")
    def delete(self, value_id):
        api = _api()
        try:
            ok = api.characteristic_api.delete_characteristic_value(value_id)
            if not ok:
                abort(500, message="PSS delete failed")
            return {"success": True, "message": "Characteristic value deleted"}
        except Exception as e:
            abort(500, message=str(e))
