"""
Documents API routes using Flask-Smorest.
"""

from flask import request, send_file
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from werkzeug.utils import secure_filename
import os
import tempfile

from ..schemas.document_schemas import (
    DocumentSchema,
    DocumentCreateSchema,
    DocumentUpdateSchema,
    DocumentListResponseSchema,
    DocumentResponseSchema,
    DocumentDetailSchema,
    DocumentReferenceCreateSchema,
    DocumentReferenceListResponseSchema,
    FileUploadResponseSchema
)
from ..schemas.common_schemas import ErrorSchema


blp = Blueprint(
    'documents',
    __name__,
    url_prefix='/api/v1/documents',
    description='Document management endpoints'
)


def get_db_api():
    """Get DatabaseAPI instance from Flask app context"""
    from tech_process_viewer import app as flask_app
    if flask_app.API is None or flask_app.API.connect_data is None:
        abort(401, message="Not connected to database. Please connect first via /api/connect")
    return flask_app.API


@blp.route('/')
class DocumentList(MethodView):
    """Document list and creation endpoints"""

    @blp.response(200, DocumentListResponseSchema)
    @blp.doc(description="Get list of documents with optional filtering")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def get(self):
        """List all documents"""
        db_api = get_db_api()

        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        name_filter = request.args.get('name', None)

        # Build filters
        filters = {}
        if name_filter:
            filters['name'] = name_filter

        # Query documents
        documents = db_api.docs_api.list_documents(
            filters=filters if filters else None,
            limit=per_page * page
        )

        # Paginate results
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_docs = documents[start_idx:end_idx]

        # Format response
        doc_list = []
        for doc in paginated_docs:
            attrs = doc.get('attributes', {})
            kind = attrs.get('kind', {})
            kind_name = None

            # Resolve kind name if kind is a reference
            if isinstance(kind, dict) and 'id' in kind:
                kind_obj = db_api.get_instance(kind['id'])
                if kind_obj:
                    kind_attrs = kind_obj.get('attributes', {})
                    kind_name = kind_attrs.get('product_data_type') or kind_attrs.get('name')

            doc_list.append({
                'document_id': doc.get('id'),
                'id': attrs.get('id'),
                'name': attrs.get('name'),
                'kind_name': kind_name,
                'version_id': attrs.get('version_id'),
                'status': attrs.get('status')
            })

        return {
            'documents': doc_list,
            'total': len(documents),
            'page': page,
            'per_page': per_page
        }

    @blp.arguments(DocumentCreateSchema)
    @blp.response(201, DocumentResponseSchema)
    @blp.doc(description="Create a new document (metadata only)")
    @blp.alt_response(400, schema=ErrorSchema, description="Invalid request")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def post(self, document_data):
        """Create a new document"""
        db_api = get_db_api()

        # Map kind_id to reference structure
        attributes = {
            'id': document_data['id'],
            'name': document_data['name']
        }

        if 'description' in document_data:
            attributes['description'] = document_data['description']

        if 'kind_id' in document_data and document_data['kind_id'] is not None:
            attributes['kind'] = {
                'id': document_data['kind_id'],
                'type': 'document_type'
            }

        if 'version_id' in document_data:
            attributes['version_id'] = document_data['version_id']

        if 'status' in document_data:
            attributes['status'] = document_data['status']

        # Create document using generic create method
        result = db_api.create_instance('apl_document', attributes)

        if result:
            created_doc = db_api.docs_api.get_document(result)
            if created_doc:
                return {
                    'success': True,
                    'message': 'Document created successfully',
                    'data': created_doc,
                    'document_id': result
                }

        abort(500, message="Failed to create document")


@blp.route('/<int:document_id>')
class DocumentDetail(MethodView):
    """Document detail, update, and delete endpoints"""

    @blp.response(200, DocumentDetailSchema)
    @blp.doc(description="Get document details by ID")
    @blp.alt_response(404, schema=ErrorSchema, description="Document not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def get(self, document_id):
        """Get document by ID"""
        db_api = get_db_api()

        document = db_api.docs_api.get_document(document_id)

        if not document:
            abort(404, message=f"Document {document_id} not found")

        return document

    @blp.arguments(DocumentUpdateSchema)
    @blp.response(200, DocumentResponseSchema)
    @blp.doc(description="Update document metadata")
    @blp.alt_response(404, schema=ErrorSchema, description="Document not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def put(self, update_data, document_id):
        """Update document"""
        db_api = get_db_api()

        # Check if document exists
        existing = db_api.docs_api.get_document(document_id)
        if not existing:
            abort(404, message=f"Document {document_id} not found")

        # Update document
        result = db_api.docs_api.update_document(document_id, update_data)

        if result:
            return {
                'success': True,
                'message': 'Document updated successfully',
                'data': result,
                'document_id': document_id
            }

        abort(500, message="Failed to update document")

    @blp.response(204)
    @blp.doc(description="Delete document")
    @blp.alt_response(404, schema=ErrorSchema, description="Document not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def delete(self, document_id):
        """Delete document"""
        db_api = get_db_api()

        # Check if document exists
        existing = db_api.docs_api.get_document(document_id)
        if not existing:
            abort(404, message=f"Document {document_id} not found")

        # Delete document (soft delete by default)
        success = db_api.docs_api.delete_document(document_id, soft_delete=True)

        if not success:
            abort(500, message="Failed to delete document")

        return '', 204


@blp.route('/<int:document_id>/upload')
class DocumentUpload(MethodView):
    """Document file upload endpoint"""

    @blp.response(200, FileUploadResponseSchema)
    @blp.doc(description="Upload file content to document")
    @blp.alt_response(404, schema=ErrorSchema, description="Document not found")
    @blp.alt_response(400, schema=ErrorSchema, description="No file provided")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def post(self, document_id):
        """Upload file to document"""
        db_api = get_db_api()

        # Check if document exists
        document = db_api.docs_api.get_document(document_id)
        if not document:
            abort(404, message=f"Document {document_id} not found")

        # Check if file is in request
        if 'file' not in request.files:
            abort(400, message="No file part in request")

        file = request.files['file']

        if file.filename == '':
            abort(400, message="No file selected")

        if file:
            # Secure filename
            filename = secure_filename(file.filename)

            # Save to temporary location
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, filename)
            file.save(temp_path)

            # Upload blob
            stored_doc_id = db_api.docs_api.upload_blob(temp_path)

            # Clean up temp file
            try:
                os.remove(temp_path)
            except:
                pass

            if stored_doc_id:
                # Update document's active version with stored document reference
                # This is simplified - full implementation would create/update apl_digital_document
                return {
                    'success': True,
                    'message': 'File uploaded successfully',
                    'document_id': document_id,
                    'filename': filename,
                    'size': file.content_length or 0
                }

            abort(500, message="Failed to upload file")


@blp.route('/<int:document_id>/download')
class DocumentDownload(MethodView):
    """Document file download endpoint"""

    @blp.doc(description="Download file content from document")
    @blp.alt_response(404, schema=ErrorSchema, description="Document or file not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def get(self, document_id):
        """Download file from document"""
        db_api = get_db_api()

        # Get document
        document = db_api.docs_api.get_document(document_id)
        if not document:
            abort(404, message=f"Document {document_id} not found")

        # Get active version and stored document reference
        attrs = document.get('attributes', {})
        active = attrs.get('active', {})

        if isinstance(active, dict) and 'id' in active:
            # Get digital document
            digital_doc = db_api.get_instance(active['id'])
            if digital_doc:
                digital_attrs = digital_doc.get('attributes', {})
                access_form = digital_attrs.get('access_form', {})

                if isinstance(access_form, dict) and 'id' in access_form:
                    # Get stored document
                    stored_doc = db_api.get_instance(access_form['id'])
                    if stored_doc:
                        stored_attrs = stored_doc.get('attributes', {})
                        file_name = stored_attrs.get('file_name', 'download')

                        # NOTE: Actual file download implementation would require
                        # fetching the blob from the backend. This is a placeholder.
                        abort(501, message="File download not yet implemented. Would download: " + file_name)

        abort(404, message="No file attached to this document")


# Document References endpoints (item-to-document links)
@blp.route('/items/<int:item_id>/documents')
class ItemDocuments(MethodView):
    """Document references for an item"""

    @blp.response(200, DocumentReferenceListResponseSchema)
    @blp.doc(description="Get all documents linked to an item")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def get(self, item_id):
        """List documents for an item"""
        db_api = get_db_api()

        # Get document references
        ref_data = db_api.docs_api.get_document_references(item_id)

        references = []
        for ref in ref_data.get('instances', []):
            ref_attrs = ref.get('attributes', {})
            assigned_doc = ref_attrs.get('assigned_document', {})

            if isinstance(assigned_doc, dict) and 'id' in assigned_doc:
                doc_sys_id = assigned_doc['id']

                # Get document details
                doc = db_api.docs_api.get_document(doc_sys_id)
                if doc:
                    doc_attrs = doc.get('attributes', {})
                    references.append({
                        'reference_id': ref.get('id'),
                        'item_id': item_id,
                        'document_id': doc_sys_id,
                        'document_name': doc_attrs.get('name', ''),
                        'document_code': doc_attrs.get('id', '')
                    })

        return {
            'item_id': item_id,
            'references': references,
            'total': len(references)
        }

    @blp.arguments(DocumentReferenceCreateSchema)
    @blp.response(201, DocumentResponseSchema)
    @blp.doc(description="Link a document to an item")
    @blp.alt_response(400, schema=ErrorSchema, description="Invalid request")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def post(self, ref_data, item_id):
        """Create document reference"""
        db_api = get_db_api()

        document_id = ref_data['document_id']
        item_id = ref_data.get('item_id', item_id)  # Allow override from body

        # Determine item type (simplified - would need proper type detection)
        item = db_api.get_instance(item_id)
        if not item:
            abort(404, message=f"Item {item_id} not found")

        item_type = item.get('type', 'apl_business_process')  # Default assumption

        # Create document reference
        result = db_api.docs_api.find_or_create_document_reference(
            doc=document_id,
            ref_object=item_id,
            ref_object_type=item_type
        )

        if result:
            ref_id, status = result
            return {
                'success': True,
                'message': f'Document reference {status}',
                'data': {'reference_id': ref_id},
                'document_id': ref_id
            }

        abort(500, message="Failed to create document reference")


@blp.route('/items/<int:item_id>/documents/<int:document_id>')
class ItemDocumentDetail(MethodView):
    """Remove document reference from item"""

    @blp.response(204)
    @blp.doc(description="Unlink document from item")
    @blp.alt_response(404, schema=ErrorSchema, description="Reference not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def delete(self, item_id, document_id):
        """Delete document reference"""
        db_api = get_db_api()

        # Find the document reference
        ref = db_api.docs_api.find_document_reference(doc=document_id, ref_object=item_id)

        if not ref:
            abort(404, message=f"Document reference not found for item {item_id} and document {document_id}")

        ref_id, status = ref

        # Delete the reference
        success = db_api.docs_api.delete_document_reference(ref_id, soft_delete=True)

        if not success:
            abort(500, message="Failed to delete document reference")

        return '', 204
