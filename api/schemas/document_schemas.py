"""
Document API schemas using Marshmallow.
"""

from marshmallow import Schema
from .fields_wrapper import Str, Int, Bool, Float, Dict, List, Nested, Raw
from .common_schemas import ReferenceSchema, SuccessResponseSchema

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


# Base Document Schema
class DocumentSchema(Schema):
    """Base schema for document data"""
    id = fields.Str(description="Document ID")
    name = fields.Str(description="Document name")
    description = fields.Str(allow_none=True, description="Document description")
    kind = fields.Nested(ReferenceSchema, allow_none=True, description="Document kind/type reference")
    version_id = fields.Str(allow_none=True, description="Version identifier")
    status = fields.Str(allow_none=True, description="Document status")
    customized = fields.Bool(allow_none=True, description="Whether document is customized")


# Document Create Schema
class DocumentCreateSchema(Schema):
    """Schema for creating a new document"""
    id = fields.Str(required=True, description="Document ID")
    name = fields.Str(required=True, description="Document name")
    description = fields.Str(allow_none=True, description="Document description")
    kind_id = fields.Int(allow_none=True, description="Document kind/type sys_id")
    version_id = fields.Str(allow_none=True, description="Version identifier")
    status = fields.Str(allow_none=True, description="Document status")


# Document Update Schema
class DocumentUpdateSchema(Schema):
    """Schema for updating document metadata"""
    name = fields.Str(allow_none=True, description="Document name")
    description = fields.Str(allow_none=True, description="Document description")
    kind_id = fields.Int(allow_none=True, description="Document kind/type sys_id")
    version_id = fields.Str(allow_none=True, description="Version identifier")
    status = fields.Str(allow_none=True, description="Document status")


# Document Detail Schema (with additional fields)
class DocumentDetailSchema(Schema):
    """Detailed schema for document with all fields"""
    sys_id = fields.Int(description="System ID")
    type = fields.Str(description="Entity type")
    access = fields.Str(description="Access level")
    attributes = fields.Nested(DocumentSchema, description="Document attributes")


# Document List Item Schema
class DocumentListItemSchema(Schema):
    """Schema for document in list view"""
    document_id = fields.Int(description="Document system ID")
    id = fields.Str(description="Document ID")
    name = fields.Str(description="Document name")
    kind_name = fields.Str(allow_none=True, description="Document kind name")
    version_id = fields.Str(allow_none=True, description="Version ID")
    status = fields.Str(allow_none=True, description="Status")


# Document List Response Schema
class DocumentListResponseSchema(Schema):
    """Schema for list of documents"""
    documents = fields.List(fields.Nested(DocumentListItemSchema), description="List of documents")
    total = fields.Int(description="Total number of documents")
    page = fields.Int(description="Current page number")
    per_page = fields.Int(description="Items per page")


# Document Response Schema
class DocumentResponseSchema(SuccessResponseSchema):
    """Schema for successful document operation response"""
    data = fields.Dict(description="Document data")
    document_id = fields.Int(description="Document system ID")


# Document Reference Create Schema
class DocumentReferenceCreateSchema(Schema):
    """Schema for creating a document reference"""
    item_id = fields.Int(required=True, description="System ID of item to link document to")
    document_id = fields.Int(required=True, description="System ID of document to link")
    reference_type = fields.Str(allow_none=True, description="Type of reference")


# Document Reference Schema
class DocumentReferenceSchema(Schema):
    """Schema for document reference"""
    reference_id = fields.Int(description="Document reference system ID")
    item_id = fields.Int(description="Item system ID")
    document_id = fields.Int(description="Document system ID")
    document_name = fields.Str(description="Document name")
    document_code = fields.Str(description="Document code/ID")


# Document Reference List Response Schema
class DocumentReferenceListResponseSchema(Schema):
    """Schema for list of document references"""
    item_id = fields.Int(description="Item system ID")
    references = fields.List(fields.Nested(DocumentReferenceSchema), description="Document references")
    total = fields.Int(description="Total number of references")


# File Upload Schema (multipart/form-data)
class FileUploadSchema(Schema):
    """Schema for file upload metadata"""
    filename = fields.Str(required=True, description="Original filename")
    content_type = fields.Str(allow_none=True, description="MIME type")
    size = fields.Int(allow_none=True, description="File size in bytes")


# File Upload Response Schema
class FileUploadResponseSchema(SuccessResponseSchema):
    """Schema for file upload response"""
    document_id = fields.Int(description="Document system ID")
    filename = fields.Str(description="Uploaded filename")
    size = fields.Int(description="File size in bytes")
