"""
Schemas for Business Process API endpoints.
"""

from marshmallow import Schema, EXCLUDE, validates, ValidationError
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


class BusinessProcessReferenceSchema(Schema):
    """Schema for business process reference objects"""
    class Meta:
        unknown = EXCLUDE

    id = fields.Int(required=True, description="Business process system ID")
    type = fields.Str(description="Entity type", dump_default="apl_business_process")


class BusinessProcessTypeSchema(Schema):
    """Schema for business process type"""
    class Meta:
        unknown = EXCLUDE

    id = fields.Int(required=True, description="Process type ID")
    name = fields.Str(description="Process type name")


class BusinessProcessElementSchema(Schema):
    """Schema for business process sub-elements (phases, technical processes)"""
    class Meta:
        unknown = EXCLUDE

    id = fields.Int(required=True, description="Element system ID")
    type = fields.Str(description="Element type")


class BusinessProcessResourceReferenceSchema(Schema):
    """Schema for business process resource reference"""
    class Meta:
        unknown = EXCLUDE

    id = fields.Int(required=True, description="Resource system ID")
    type = fields.Str(description="Resource type")


class BusinessProcessAttributesSchema(Schema):
    """Schema for business process attributes"""
    class Meta:
        unknown = EXCLUDE

    id = fields.Str(description="Business process ID (business key)")
    name = fields.Str(required=True, description="Process name")
    description = fields.Str(description="Process description", load_default="")
    customized = fields.Bool(description="Whether process is customized", dump_default=False)
    type = fields.Nested(BusinessProcessTypeSchema, description="Process type reference")
    elements = fields.List(fields.Nested(BusinessProcessElementSchema), description="Sub-processes/phases")
    resources = fields.List(fields.Nested(BusinessProcessResourceReferenceSchema), description="Process resources")


class BusinessProcessSchema(Schema):
    """Schema for full business process object"""
    class Meta:
        unknown = EXCLUDE

    id = fields.Int(required=True, description="System ID")
    type = fields.Str(required=True, description="Entity type", dump_default="apl_business_process")
    access = fields.Str(description="Access level")
    attributes = fields.Nested(BusinessProcessAttributesSchema, required=True)


class BusinessProcessCreateSchema(Schema):
    """Schema for creating a new business process"""
    class Meta:
        unknown = EXCLUDE

    id = fields.Str(description="Business process ID (optional, will be generated if not provided)")
    name = fields.Str(required=True, description="Process name")
    description = fields.Str(description="Process description", load_default="")
    customized = fields.Bool(description="Whether process is customized", load_default=False)
    type_id = fields.Int(description="Process type system ID")
    parent_id = fields.Int(description="Parent process ID (if this is a sub-process)")

    @validates('name')
    def validate_name(self, value):
        if not value or not value.strip():
            raise ValidationError("Process name cannot be empty")


class BusinessProcessUpdateSchema(Schema):
    """Schema for updating an existing business process"""
    class Meta:
        unknown = EXCLUDE

    name = fields.Str(description="Process name")
    description = fields.Str(description="Process description")
    customized = fields.Bool(description="Whether process is customized")
    type_id = fields.Int(description="Process type system ID")


class BusinessProcessListItemSchema(Schema):
    """Schema for business process in list view"""
    class Meta:
        unknown = EXCLUDE

    process_id = fields.Int(required=True, description="Process system ID")
    name = fields.Str(required=True, description="Process name")
    description = fields.Str(description="Process description")
    process_type = fields.Str(description="Process type (Typical/Customized)")
    org_unit = fields.Str(description="Organizational unit")
    customized = fields.Bool(description="Whether process is customized")


class BusinessProcessDetailSchema(Schema):
    """Schema for detailed business process view"""
    class Meta:
        unknown = EXCLUDE

    process_id = fields.Int(required=True, description="Process system ID")
    name = fields.Str(required=True, description="Process name")
    description = fields.Str(description="Process description")
    process_type = fields.Str(description="Process type (Typical/Customized)")
    org_unit = fields.Str(description="Organizational unit")
    customized = fields.Bool(description="Whether process is customized")
    elements = fields.List(fields.Nested(BusinessProcessListItemSchema), description="Sub-processes")
    resources = fields.List(fields.Dict(), description="Process resources")
    documents = fields.List(fields.Dict(), description="Related documents")


class BusinessProcessElementCreateSchema(Schema):
    """Schema for adding a sub-process/phase to a business process"""
    class Meta:
        unknown = EXCLUDE

    element_id = fields.Int(required=True, description="ID of existing process to add as sub-element")

    @validates('element_id')
    def validate_element_id(self, value):
        if value <= 0:
            raise ValidationError("Element ID must be a positive integer")


class BusinessProcessResourceCreateSchema(Schema):
    """Schema for adding a resource to a business process"""
    class Meta:
        unknown = EXCLUDE

    type_id = fields.Int(required=True, description="Resource type ID")
    object_id = fields.Int(description="Object ID (organization, product, etc.)")
    value_component = fields.Float(description="Resource value (e.g., time in hours)")
    unit_id = fields.Int(description="Unit of measurement ID")

    @validates('type_id')
    def validate_type_id(self, value):
        if value <= 0:
            raise ValidationError("Resource type ID must be a positive integer")


class BusinessProcessResourceUpdateSchema(Schema):
    """Schema for updating a business process resource"""
    class Meta:
        unknown = EXCLUDE

    value_component = fields.Float(description="Resource value")
    object_id = fields.Int(description="Object ID")
    unit_id = fields.Int(description="Unit ID")


class BusinessProcessResponseSchema(Schema):
    """Schema for successful business process operation response"""
    class Meta:
        unknown = EXCLUDE

    success = fields.Bool(required=True, description="Operation success")
    message = fields.Str(description="Response message")
    data = fields.Nested(BusinessProcessSchema, description="Business process data")
    process_id = fields.Int(description="Created/updated process ID")
    resource_id = fields.Int(description="Resource ID (returned from resource-add endpoints)", allow_none=True)


class BusinessProcessListResponseSchema(Schema):
    """Schema for list of business processes"""
    class Meta:
        unknown = EXCLUDE

    processes = fields.List(fields.Nested(BusinessProcessListItemSchema), required=True)
    total = fields.Int(description="Total number of processes")
    page = fields.Int(description="Current page")
    per_page = fields.Int(description="Items per page")
