"""
Common schemas used across all API endpoints.
"""

from marshmallow import Schema, EXCLUDE
from .fields_wrapper import Str, Int, Bool, Float, Dict, List, Nested, Raw

# Используем псевдоним fields для совместимости
class fields:
    Str = Str
    Int = Int
    Bool = Bool
    Float = Float
    Dict = Dict
    List = List
    Nested = Nested
    Raw = Raw


class ErrorSchema(Schema):
    """Schema for error responses"""
    class Meta:
        unknown = EXCLUDE

    error = fields.Str(required=True, description="Error message")
    message = fields.Str(description="Detailed error description")
    status_code = fields.Int(description="HTTP status code")
    details = fields.Dict(description="Additional error details")


class SuccessResponseSchema(Schema):
    """Schema for simple success responses"""
    class Meta:
        unknown = EXCLUDE

    success = fields.Bool(required=True, description="Operation success status")
    message = fields.Str(description="Success message")
    data = fields.Dict(description="Response data")


class PaginationSchema(Schema):
    """Schema for pagination metadata"""
    class Meta:
        unknown = EXCLUDE

    page = fields.Int(description="Current page number", dump_default=1)
    per_page = fields.Int(description="Items per page", dump_default=100)
    total = fields.Int(description="Total number of items")
    pages = fields.Int(description="Total number of pages")


class PaginatedResponseSchema(Schema):
    """Schema for paginated list responses"""
    class Meta:
        unknown = EXCLUDE

    items = fields.List(fields.Dict(), required=True, description="List of items")
    pagination = fields.Nested(PaginationSchema, description="Pagination metadata")


class ReferenceSchema(Schema):
    """Schema for object references (id + type)"""
    class Meta:
        unknown = EXCLUDE

    id = fields.Int(required=True, description="Object system ID")
    type = fields.Str(description="Object type")


class APLInstanceBaseSchema(Schema):
    """Base schema for APL instance objects"""
    class Meta:
        unknown = EXCLUDE

    id = fields.Int(required=True, description="System ID")
    type = fields.Str(required=True, description="Entity type")
    access = fields.Str(description="Access level")
    attributes = fields.Dict(description="Object attributes")


class SessionSchema(Schema):
    """Schema for session/connection data"""
    class Meta:
        unknown = EXCLUDE

    session_key = fields.Str(required=True, description="Session key for authentication")
    connected = fields.Bool(description="Connection status")
    db = fields.Str(description="Database name")
    user = fields.Str(description="Username")


class ConnectionRequestSchema(Schema):
    """Schema for database connection request"""
    class Meta:
        unknown = EXCLUDE

    server_port = fields.Str(description="Database server URL", dump_default="http://localhost:7239")
    db = fields.Str(required=True, description="Database name")
    user = fields.Str(required=True, description="Username")
    password = fields.Str(load_default="", description="Password (if required)")


class QueryFilterSchema(Schema):
    """Schema for query filters"""
    class Meta:
        unknown = EXCLUDE

    field = fields.Str(required=True, description="Field name to filter on")
    operator = fields.Str(description="Comparison operator (=, >, <, LIKE, IN, etc.)", dump_default="=")
    value = fields.Raw(required=True, description="Filter value")


class QueryParametersSchema(Schema):
    """Schema for common query parameters"""
    class Meta:
        unknown = EXCLUDE

    page = fields.Int(description="Page number", dump_default=1, load_default=1)
    per_page = fields.Int(description="Items per page", dump_default=100, load_default=100)
    sort_by = fields.Str(description="Field to sort by")
    sort_order = fields.Str(description="Sort order (asc or desc)", dump_default="asc")
    filters = fields.List(fields.Nested(QueryFilterSchema), description="List of filters")
