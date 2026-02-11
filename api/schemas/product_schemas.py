"""
Schemas for Products API endpoints.
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


class ProductReferenceSchema(Schema):
    """Schema for product reference objects"""
    class Meta:
        unknown = EXCLUDE

    id = fields.Int(required=True, description="Product system ID")
    type = fields.Str(description="Entity type", dump_default="product")


class ProductDefinitionReferenceSchema(Schema):
    """Schema for product definition reference"""
    class Meta:
        unknown = EXCLUDE

    id = fields.Int(required=True, description="Product definition system ID")
    type = fields.Str(description="Entity type", dump_default="apl_product_definition_formation")


class ProductAttributesSchema(Schema):
    """Schema for product attributes"""
    class Meta:
        unknown = EXCLUDE

    id = fields.Str(description="Product ID (business key)")
    name = fields.Str(required=True, description="Product name")
    description = fields.Str(description="Product description", load_default="")
    code = fields.Str(description="Product code")
    guid = fields.Str(description="Global unique identifier")


class ProductSchema(Schema):
    """Schema for full product object"""
    class Meta:
        unknown = EXCLUDE

    id = fields.Int(required=True, description="System ID")
    type = fields.Str(required=True, description="Entity type", dump_default="product")
    access = fields.Str(description="Access level")
    attributes = fields.Nested(ProductAttributesSchema, required=True)


class ProductCreateSchema(Schema):
    """Schema for creating a new product"""
    class Meta:
        unknown = EXCLUDE

    id = fields.Str(description="Product ID (optional, will be generated if not provided)")
    name = fields.Str(required=True, description="Product name")
    description = fields.Str(description="Product description", load_default="")
    code = fields.Str(description="Product code")
    guid = fields.Str(description="Global unique identifier")

    @validates('name')
    def validate_name(self, value):
        if not value or not value.strip():
            raise ValidationError("Product name cannot be empty")


class ProductUpdateSchema(Schema):
    """Schema for updating an existing product"""
    class Meta:
        unknown = EXCLUDE

    name = fields.Str(description="Product name")
    description = fields.Str(description="Product description")
    code = fields.Str(description="Product code")


class ProductListItemSchema(Schema):
    """Schema for product in list view"""
    class Meta:
        unknown = EXCLUDE

    product_id = fields.Int(required=True, description="Product system ID")
    id = fields.Str(description="Product business ID")
    name = fields.Str(required=True, description="Product name")
    description = fields.Str(description="Product description")
    code = fields.Str(description="Product code")
    has_versions = fields.Bool(description="Whether product has versions")


class ProductDefinitionAttributesSchema(Schema):
    """Schema for product definition attributes"""
    class Meta:
        unknown = EXCLUDE

    id = fields.Str(description="Definition ID")
    description = fields.Str(description="Definition description")
    code1 = fields.Str(description="Code 1")
    code2 = fields.Str(description="Code 2")
    of_product = fields.Nested(ProductReferenceSchema, description="Reference to product")


class ProductDefinitionFormationSchema(Schema):
    """Schema for product definition formation"""
    class Meta:
        unknown = EXCLUDE

    id = fields.Int(required=True, description="Formation system ID")
    type = fields.Str(description="Entity type", dump_default="apl_product_definition_formation")
    attributes = fields.Nested(ProductDefinitionAttributesSchema)


class ProductDefinitionCreateSchema(Schema):
    """Schema for creating product definition/version"""
    class Meta:
        unknown = EXCLUDE

    id = fields.Str(description="Definition ID")
    description = fields.Str(required=True, description="Version description")
    code1 = fields.Str(description="Code 1")
    code2 = fields.Str(description="Code 2")


class ProductDefinitionUpdateSchema(Schema):
    """Schema for updating product definition"""
    class Meta:
        unknown = EXCLUDE

    description = fields.Str(description="Version description")
    code1 = fields.Str(description="Code 1")
    code2 = fields.Str(description="Code 2")


class BOMItemAttributesSchema(Schema):
    """Schema for BOM item (assembly component usage) attributes"""
    class Meta:
        unknown = EXCLUDE

    reference_designator = fields.Str(description="Component designation (e.g., R1, C2)")
    value_component = fields.Float(description="Quantity")
    unit_component = fields.Dict(description="Unit of measurement")
    relating_product_definition = fields.Dict(description="Parent product definition")
    related_product_definition = fields.Dict(description="Child product definition (component)")


class BOMItemSchema(Schema):
    """Schema for BOM item"""
    class Meta:
        unknown = EXCLUDE

    id = fields.Int(required=True, description="BOM item system ID")
    type = fields.Str(description="Entity type")
    attributes = fields.Nested(BOMItemAttributesSchema)


class BOMItemCreateSchema(Schema):
    """Schema for creating BOM item"""
    class Meta:
        unknown = EXCLUDE

    component_id = fields.Int(required=True, description="Component product definition ID")
    quantity = fields.Float(required=True, description="Quantity")
    unit_id = fields.Int(description="Unit of measurement ID")
    reference_designator = fields.Str(description="Reference designator (e.g., R1, C2)")

    @validates('quantity')
    def validate_quantity(self, value):
        if value <= 0:
            raise ValidationError("Quantity must be positive")


class BOMItemUpdateSchema(Schema):
    """Schema for updating BOM item"""
    class Meta:
        unknown = EXCLUDE

    quantity = fields.Float(description="Quantity")
    unit_id = fields.Int(description="Unit of measurement ID")
    reference_designator = fields.Str(description="Reference designator")


class BOMStructureSchema(Schema):
    """Schema for BOM structure (hierarchy)"""
    class Meta:
        unknown = EXCLUDE

    product_definition_id = fields.Int(required=True, description="Product definition ID")
    product_name = fields.Str(description="Product name")
    components = fields.List(fields.Nested(BOMItemSchema), description="List of components")
    total_components = fields.Int(description="Total number of components")


class ProductResponseSchema(Schema):
    """Schema for successful product operation response"""
    class Meta:
        unknown = EXCLUDE

    success = fields.Bool(required=True, description="Operation success")
    message = fields.Str(description="Response message")
    data = fields.Nested(ProductSchema, description="Product data")
    product_id = fields.Int(description="Created/updated product ID")


class ProductListResponseSchema(Schema):
    """Schema for list of products"""
    class Meta:
        unknown = EXCLUDE

    products = fields.List(fields.Nested(ProductListItemSchema), required=True)
    total = fields.Int(description="Total number of products")
    page = fields.Int(description="Current page")
    per_page = fields.Int(description="Items per page")


class ProductDefinitionResponseSchema(Schema):
    """Schema for product definition response"""
    class Meta:
        unknown = EXCLUDE

    success = fields.Bool(required=True, description="Operation success")
    message = fields.Str(description="Response message")
    data = fields.Nested(ProductDefinitionFormationSchema, description="Product definition data")
    definition_id = fields.Int(description="Created/updated definition ID")


class ProductDefinitionListResponseSchema(Schema):
    """Schema for list of product definitions"""
    class Meta:
        unknown = EXCLUDE

    product_id = fields.Int(required=True, description="Product system ID")
    definitions = fields.List(fields.Nested(ProductDefinitionFormationSchema), required=True)
    total = fields.Int(description="Total number of versions")


class BOMResponseSchema(Schema):
    """Schema for BOM operation response"""
    class Meta:
        unknown = EXCLUDE

    success = fields.Bool(required=True, description="Operation success")
    message = fields.Str(description="Response message")
    data = fields.Nested(BOMItemSchema, description="BOM item data")
    bom_item_id = fields.Int(description="BOM item ID")


class ProductDetailSchema(Schema):
    """Schema for detailed product view"""
    class Meta:
        unknown = EXCLUDE

    product = fields.Nested(ProductSchema, required=True)
    definitions = fields.List(fields.Nested(ProductDefinitionFormationSchema), description="Product versions")
    definition_count = fields.Int(description="Number of versions")
