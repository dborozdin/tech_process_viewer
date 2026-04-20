"""OpenAPI/Swagger path descriptions for CRUD endpoints.

25 endpoints live in api/routes/crud_routes.py as a plain Flask Blueprint
(no flask-smorest). To make them appear in Swagger UI and openapi.json/yaml,
we monkey-patch api.spec.to_dict() to inject extra paths after Smorest finishes
its own collection.

Применение:
    from tech_process_viewer.api.openapi_crud_paths import register_crud_paths
    register_crud_paths(api)
"""


_OK = {
    "description": "Success",
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "message": {"type": "string"},
                    "data": {"type": "object"},
                }
            }
        }
    }
}

_CREATED = {
    "description": "Created",
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "message": {"type": "string"},
                    "data": {"type": "object"},
                }
            }
        }
    }
}

_BAD_REQUEST = {"description": "Bad request — missing/invalid parameters"}
_UNAUTHORIZED = {"description": "Not connected to DB. POST /api/connect first."}
_NOT_FOUND = {"description": "Entity not found"}
_SERVER_ERROR = {"description": "Server / PSS error"}


def _path_param(name: str, descr: str = ""):
    return {
        "name": name,
        "in": "path",
        "required": True,
        "schema": {"type": "integer"},
        "description": descr,
    }


def _json_body(properties: dict, required: list = None):
    return {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": required or [],
                    "properties": properties,
                }
            }
        }
    }


def _build_crud_paths():
    """Build the dict of OpenAPI paths for CRUD endpoints."""
    paths = {}

    # ========== Products ==========
    paths["/api/products"] = {
        "post": {
            "tags": ["CRUD: Products"],
            "summary": "Создать изделие",
            "description": "Создаёт apl_product_definition_formation, добавляет в папку Aircrafts.",
            "requestBody": _json_body({
                "id": {"type": "string", "example": "TEST-PRD-001"},
                "name": {"type": "string", "example": "Test Product"},
                "type": {"type": "string", "default": "make"},
                "source": {"type": "string", "default": "make"},
            }, ["id", "name"]),
            "responses": {
                "201": _CREATED, "401": _UNAUTHORIZED, "500": _SERVER_ERROR,
            }
        }
    }

    paths["/api/products/{pdf_id}"] = {
        "put": {
            "tags": ["CRUD: Products"],
            "summary": "Обновить изделие",
            "parameters": [_path_param("pdf_id", "sys_id of apl_product_definition_formation")],
            "requestBody": _json_body({
                "id": {"type": "string"},
                "name": {"type": "string"},
            }),
            "responses": {"200": _OK, "401": _UNAUTHORIZED, "404": _NOT_FOUND, "500": _SERVER_ERROR}
        },
        "delete": {
            "tags": ["CRUD: Products"],
            "summary": "Удалить изделие",
            "parameters": [_path_param("pdf_id", "sys_id of apl_product_definition_formation")],
            "responses": {"200": _OK, "401": _UNAUTHORIZED, "500": _SERVER_ERROR}
        }
    }

    # ========== BOM ==========
    paths["/api/products/bom"] = {
        "post": {
            "tags": ["CRUD: BOM"],
            "summary": "Создать BOM-связь (родитель ↔ компонент)",
            "requestBody": _json_body({
                "relating_pdf_id": {"type": "integer", "description": "Parent PDF sys_id"},
                "related_pdf_id": {"type": "integer", "description": "Component PDF sys_id"},
                "quantity": {"type": "number", "default": 1},
                "unit_id": {"type": "integer", "description": "Optional apl_unit sys_id"},
            }, ["relating_pdf_id", "related_pdf_id"]),
            "responses": {"201": _CREATED, "400": _BAD_REQUEST, "401": _UNAUTHORIZED, "500": _SERVER_ERROR}
        }
    }

    paths["/api/products/bom/{bom_id}"] = {
        "delete": {
            "tags": ["CRUD: BOM"],
            "summary": "Удалить BOM-связь",
            "parameters": [_path_param("bom_id", "BOM link sys_id")],
            "responses": {"200": _OK, "401": _UNAUTHORIZED, "500": _SERVER_ERROR}
        }
    }

    paths["/api/products/{pdf_id}/bom"] = {
        "get": {
            "tags": ["CRUD: BOM"],
            "summary": "Получить структуру BOM для изделия",
            "parameters": [_path_param("pdf_id", "Product PDF sys_id")],
            "responses": {"200": _OK, "401": _UNAUTHORIZED, "500": _SERVER_ERROR}
        }
    }

    # ========== Business Processes ==========
    paths["/api/business-processes"] = {
        "post": {
            "tags": ["CRUD: Business Processes"],
            "summary": "Создать бизнес-процесс",
            "requestBody": _json_body({
                "id": {"type": "string", "example": "TEST-BP-001"},
                "name": {"type": "string", "example": "Test Process"},
                "description": {"type": "string"},
                "type_name": {"type": "string", "default": "Default"},
            }, ["name"]),
            "responses": {"201": _CREATED, "401": _UNAUTHORIZED, "500": _SERVER_ERROR}
        }
    }

    paths["/api/business-processes/{bp_id}"] = {
        "put": {
            "tags": ["CRUD: Business Processes"],
            "summary": "Обновить бизнес-процесс",
            "parameters": [_path_param("bp_id")],
            "requestBody": _json_body({
                "name": {"type": "string"},
                "description": {"type": "string"},
            }),
            "responses": {"200": _OK, "401": _UNAUTHORIZED, "500": _SERVER_ERROR}
        },
        "delete": {
            "tags": ["CRUD: Business Processes"],
            "summary": "Удалить бизнес-процесс",
            "parameters": [_path_param("bp_id")],
            "responses": {"200": _OK, "401": _UNAUTHORIZED, "500": _SERVER_ERROR}
        }
    }

    paths["/api/business-processes/{bp_id}/elements"] = {
        "post": {
            "tags": ["CRUD: Business Processes"],
            "summary": "Добавить вложенный элемент в процесс",
            "parameters": [_path_param("bp_id", "Parent process sys_id")],
            "requestBody": _json_body({
                "element_id": {"type": "integer", "description": "Child process sys_id"},
            }, ["element_id"]),
            "responses": {"201": _CREATED, "400": _BAD_REQUEST, "401": _UNAUTHORIZED, "500": _SERVER_ERROR}
        }
    }

    paths["/api/business-processes/{bp_id}/elements/{child_id}"] = {
        "delete": {
            "tags": ["CRUD: Business Processes"],
            "summary": "Удалить вложенный элемент из процесса",
            "parameters": [
                _path_param("bp_id", "Parent process sys_id"),
                _path_param("child_id", "Child element sys_id"),
            ],
            "responses": {"200": _OK, "401": _UNAUTHORIZED, "500": _SERVER_ERROR}
        }
    }

    paths["/api/business-processes/{bp_id}/link-product"] = {
        "post": {
            "tags": ["CRUD: Business Processes"],
            "summary": "Привязать процесс к изделию",
            "parameters": [_path_param("bp_id")],
            "requestBody": _json_body({
                "pdf_id": {"type": "integer", "description": "Product PDF sys_id"},
            }, ["pdf_id"]),
            "responses": {"201": _CREATED, "400": _BAD_REQUEST, "401": _UNAUTHORIZED, "500": _SERVER_ERROR}
        }
    }

    # ========== Documents ==========
    paths["/api/documents/upload"] = {
        "post": {
            "tags": ["CRUD: Documents"],
            "summary": "Загрузить файл-документ (multipart/form-data)",
            "requestBody": {
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "required": ["file"],
                            "properties": {
                                "file": {"type": "string", "format": "binary"},
                                "doc_id": {"type": "string"},
                                "doc_name": {"type": "string"},
                                "doc_type_id": {"type": "integer"},
                                "item_id": {"type": "integer"},
                                "item_type": {"type": "string", "default": "apl_business_process"},
                            }
                        }
                    }
                }
            },
            "responses": {"201": _CREATED, "400": _BAD_REQUEST, "401": _UNAUTHORIZED, "500": _SERVER_ERROR}
        }
    }

    paths["/api/document-references"] = {
        "post": {
            "tags": ["CRUD: Documents"],
            "summary": "Создать ссылку документ → объект",
            "requestBody": _json_body({
                "doc_id": {"type": "integer", "description": "Document sys_id"},
                "item_id": {"type": "integer", "description": "Item sys_id"},
                "item_type": {"type": "string", "default": "apl_business_process"},
            }, ["doc_id", "item_id"]),
            "responses": {"201": _CREATED, "400": _BAD_REQUEST, "401": _UNAUTHORIZED, "500": _SERVER_ERROR}
        }
    }

    paths["/api/document-references/{ref_id}"] = {
        "delete": {
            "tags": ["CRUD: Documents"],
            "summary": "Удалить ссылку документ → объект",
            "parameters": [_path_param("ref_id", "apl_document_reference sys_id")],
            "responses": {"200": _OK, "401": _UNAUTHORIZED, "500": _SERVER_ERROR}
        }
    }

    paths["/api/documents/search"] = {
        "get": {
            "tags": ["CRUD: Documents"],
            "summary": "Поиск документов по id (substring LIKE)",
            "parameters": [{
                "name": "q",
                "in": "query",
                "required": False,
                "schema": {"type": "string"},
                "description": "Search substring",
            }],
            "responses": {"200": _OK, "401": _UNAUTHORIZED, "500": _SERVER_ERROR}
        }
    }

    # ========== Characteristics ==========
    paths["/api/characteristics"] = {
        "get": {
            "tags": ["CRUD: Characteristics"],
            "summary": "Список определений характеристик",
            "responses": {"200": _OK, "401": _UNAUTHORIZED, "500": _SERVER_ERROR}
        }
    }

    paths["/api/characteristics/values/{item_id}"] = {
        "get": {
            "tags": ["CRUD: Characteristics"],
            "summary": "Значения характеристик объекта",
            "parameters": [_path_param("item_id", "Owner sys_id (PDF/BP/etc.)")],
            "responses": {"200": _OK, "401": _UNAUTHORIZED, "500": _SERVER_ERROR}
        }
    }

    paths["/api/characteristics/values"] = {
        "post": {
            "tags": ["CRUD: Characteristics"],
            "summary": "Создать значение характеристики",
            "requestBody": _json_body({
                "item_id": {"type": "integer"},
                "characteristic_id": {"type": "integer"},
                "value": {"type": "string"},
                "subtype": {"type": "string", "default": "apl_descriptive_characteristic_value"},
            }, ["item_id", "characteristic_id"]),
            "responses": {"201": _CREATED, "400": _BAD_REQUEST, "401": _UNAUTHORIZED, "500": _SERVER_ERROR}
        }
    }

    paths["/api/characteristics/values/{value_id}"] = {
        "put": {
            "tags": ["CRUD: Characteristics"],
            "summary": "Обновить значение характеристики",
            "parameters": [_path_param("value_id")],
            "requestBody": _json_body({
                "value": {"type": "string"},
                "subtype": {"type": "string", "default": "apl_descriptive_characteristic_value"},
            }, ["value"]),
            "responses": {"200": _OK, "401": _UNAUTHORIZED, "500": _SERVER_ERROR}
        },
        "delete": {
            "tags": ["CRUD: Characteristics"],
            "summary": "Удалить значение характеристики",
            "parameters": [_path_param("value_id")],
            "responses": {"200": _OK, "401": _UNAUTHORIZED, "500": _SERVER_ERROR}
        }
    }

    # ========== Resources ==========
    paths["/api/resources"] = {
        "post": {
            "tags": ["CRUD: Resources"],
            "summary": "Создать ресурс процесса",
            "requestBody": _json_body({
                "process_id": {"type": "integer", "description": "Owner BP sys_id"},
                "type_id": {"type": "integer", "description": "Resource type sys_id"},
                "id": {"type": "string"},
                "name": {"type": "string"},
                "object_id": {"type": "integer"},
                "object_type": {"type": "string", "default": "organization"},
                "value_component": {"type": "number"},
                "unit_id": {"type": "integer"},
            }, ["process_id", "type_id"]),
            "responses": {"201": _CREATED, "400": _BAD_REQUEST, "401": _UNAUTHORIZED, "500": _SERVER_ERROR}
        }
    }

    paths["/api/resources/{resource_id}"] = {
        "put": {
            "tags": ["CRUD: Resources"],
            "summary": "Обновить ресурс",
            "parameters": [_path_param("resource_id")],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "additionalProperties": True,
                        }
                    }
                }
            },
            "responses": {"200": _OK, "401": _UNAUTHORIZED, "500": _SERVER_ERROR}
        },
        "delete": {
            "tags": ["CRUD: Resources"],
            "summary": "Удалить ресурс",
            "parameters": [_path_param("resource_id")],
            "responses": {"200": _OK, "401": _UNAUTHORIZED, "500": _SERVER_ERROR}
        }
    }

    paths["/api/resource-types"] = {
        "get": {
            "tags": ["CRUD: Resources"],
            "summary": "Список типов ресурсов",
            "responses": {"200": _OK, "401": _UNAUTHORIZED, "500": _SERVER_ERROR}
        }
    }

    return paths


def register_crud_paths(api):
    """Monkey-patch api.spec.to_dict() to inject CRUD paths.

    Smorest serves /api/openapi.json by calling api.spec.to_dict() each time, so
    wrapping it injects our extra paths into Swagger UI without re-implementing
    the endpoints in flask-smorest.
    """
    crud_paths = _build_crud_paths()
    orig_to_dict = api.spec.to_dict

    def patched_to_dict(*args, **kwargs):
        spec_dict = orig_to_dict(*args, **kwargs)
        spec_dict.setdefault("paths", {}).update(crud_paths)
        return spec_dict

    api.spec.to_dict = patched_to_dict
