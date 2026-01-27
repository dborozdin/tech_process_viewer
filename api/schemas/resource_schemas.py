"""
Resources and Organizations API schemas using Marshmallow.
"""

from marshmallow import Schema, fields
from .common_schemas import ReferenceSchema, SuccessResponseSchema


# ========== Resource Schemas ==========

# Base Resource Schema
class ResourceSchema(Schema):
    """Base schema for resource data"""
    value_component = fields.Float(allow_none=True, description="Resource quantity/value")
    unit_component = fields.Nested(ReferenceSchema, allow_none=True, description="Unit reference")
    object = fields.Nested(ReferenceSchema, allow_none=True, description="Resource object reference")
    type = fields.Nested(ReferenceSchema, allow_none=True, description="Resource type reference")
    process = fields.Nested(ReferenceSchema, allow_none=True, description="Business process reference")


# Resource Create Schema
class ResourceCreateSchema(Schema):
    """Schema for creating a new resource"""
    process_id = fields.Int(required=True, description="Business process system ID")
    type_id = fields.Int(required=True, description="Resource type system ID")
    object_id = fields.Int(allow_none=True, description="Resource object system ID")
    value_component = fields.Float(allow_none=True, description="Resource quantity/value")
    unit_id = fields.Int(allow_none=True, description="Unit system ID")


# Resource Update Schema
class ResourceUpdateSchema(Schema):
    """Schema for updating a resource"""
    value_component = fields.Float(allow_none=True, description="Resource quantity/value")
    unit_id = fields.Int(allow_none=True, description="Unit system ID")
    object_id = fields.Int(allow_none=True, description="Resource object system ID")


# Resource Detail Schema
class ResourceDetailSchema(Schema):
    """Detailed schema for resource with all fields"""
    sys_id = fields.Int(description="System ID")
    type = fields.Str(description="Entity type")
    access = fields.Str(description="Access level")
    attributes = fields.Nested(ResourceSchema, description="Resource attributes")


# Resource List Item Schema
class ResourceListItemSchema(Schema):
    """Schema for resource in list view"""
    resource_id = fields.Int(description="Resource system ID")
    process_id = fields.Int(allow_none=True, description="Business process ID")
    type_name = fields.Str(allow_none=True, description="Resource type name")
    value_component = fields.Float(allow_none=True, description="Quantity/value")
    unit_name = fields.Str(allow_none=True, description="Unit name")


# Resource List Response Schema
class ResourceListResponseSchema(Schema):
    """Schema for list of resources"""
    resources = fields.List(fields.Nested(ResourceListItemSchema), description="List of resources")
    total = fields.Int(description="Total number of resources")
    page = fields.Int(description="Current page number")
    per_page = fields.Int(description="Items per page")


# Resource Response Schema
class ResourceResponseSchema(SuccessResponseSchema):
    """Schema for successful resource operation response"""
    data = fields.Dict(description="Resource data")
    resource_id = fields.Int(description="Resource system ID")


# Resource Type Schema
class ResourceTypeSchema(Schema):
    """Schema for resource type"""
    id = fields.Str(description="Resource type ID")
    name = fields.Str(description="Resource type name")
    description = fields.Str(allow_none=True, description="Description")


# Resource Type List Response Schema
class ResourceTypeListResponseSchema(Schema):
    """Schema for list of resource types"""
    resource_types = fields.List(fields.Nested(ResourceTypeSchema), description="List of resource types")
    total = fields.Int(description="Total number of types")


# ========== Organization Schemas ==========

# Base Organization Schema
class OrganizationSchema(Schema):
    """Base schema for organization data"""
    id = fields.Str(description="Organization ID")
    name = fields.Str(description="Organization name")
    description = fields.Str(allow_none=True, description="Description")
    customized = fields.Bool(allow_none=True, description="Whether organization is customized")


# Organization Create Schema
class OrganizationCreateSchema(Schema):
    """Schema for creating a new organization"""
    id = fields.Str(required=True, description="Organization ID")
    name = fields.Str(required=True, description="Organization name")
    description = fields.Str(allow_none=True, description="Description")


# Organization Update Schema
class OrganizationUpdateSchema(Schema):
    """Schema for updating an organization"""
    name = fields.Str(allow_none=True, description="Organization name")
    description = fields.Str(allow_none=True, description="Description")


# Organization Detail Schema
class OrganizationDetailSchema(Schema):
    """Detailed schema for organization with all fields"""
    sys_id = fields.Int(description="System ID")
    type = fields.Str(description="Entity type")
    access = fields.Str(description="Access level")
    attributes = fields.Nested(OrganizationSchema, description="Organization attributes")


# Organization List Item Schema
class OrganizationListItemSchema(Schema):
    """Schema for organization in list view"""
    organization_id = fields.Int(description="Organization system ID")
    id = fields.Str(description="Organization ID")
    name = fields.Str(description="Organization name")
    description = fields.Str(allow_none=True, description="Description")


# Organization List Response Schema
class OrganizationListResponseSchema(Schema):
    """Schema for list of organizations"""
    organizations = fields.List(fields.Nested(OrganizationListItemSchema), description="List of organizations")
    total = fields.Int(description="Total number of organizations")
    page = fields.Int(description="Current page number")
    per_page = fields.Int(description="Items per page")


# Organization Response Schema
class OrganizationResponseSchema(SuccessResponseSchema):
    """Schema for successful organization operation response"""
    data = fields.Dict(description="Organization data")
    organization_id = fields.Int(description="Organization system ID")
