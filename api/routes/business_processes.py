"""
Business Processes API routes using Flask-Smorest.
"""

from flask import request, current_app
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from ..schemas.bp_schemas import (
    BusinessProcessSchema,
    BusinessProcessCreateSchema,
    BusinessProcessUpdateSchema,
    BusinessProcessListResponseSchema,
    BusinessProcessResponseSchema,
    BusinessProcessElementCreateSchema,
    BusinessProcessResourceCreateSchema,
    BusinessProcessResourceUpdateSchema,
    BusinessProcessDetailSchema
)
from ..schemas.common_schemas import ErrorSchema


blp = Blueprint(
    'business_processes',
    __name__,
    url_prefix='/api/v1/business-processes',
    description='Business process management endpoints'
)


def get_db_api():
    """Get DatabaseAPI instance from Flask app context"""
    from tech_process_viewer.api.app_helpers import get_api
    api = get_api()
    if api is None or api.connect_data is None:
        abort(401, message="Not connected to database. Please connect first via /api/connect")
    return api


@blp.route('/')
class BusinessProcessList(MethodView):
    """Business process list and creation endpoints"""

    @blp.response(200, BusinessProcessListResponseSchema)
    @blp.doc(description="Get list of business processes with optional filtering")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def get(self):
        """List all business processes"""
        db_api = get_db_api()

        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 100, type=int)
        name_filter = request.args.get('name', None)
        customized_filter = request.args.get('customized', None)

        # Build filters
        filters = {}
        if name_filter:
            filters['name'] = name_filter
        if customized_filter is not None:
            filters['customized'] = customized_filter.lower() == 'true'

        # Query business processes
        processes = db_api.bp_api.list_business_processes(
            filters=filters if filters else None,
            limit=per_page * page
        )

        # Paginate results
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_processes = processes[start_idx:end_idx]

        # Format response
        process_list = []
        for proc in paginated_processes:
            attrs = proc.get('attributes', {})
            process_list.append({
                'process_id': proc.get('id'),
                'name': attrs.get('name'),
                'description': attrs.get('description', ''),
                'process_type': 'Customized' if attrs.get('customized', False) else 'Typical',
                'org_unit': '',  # Will be populated from resources if needed
                'customized': attrs.get('customized', False)
            })

        return {
            'processes': process_list,
            'total': len(processes),
            'page': page,
            'per_page': per_page
        }

    @blp.arguments(BusinessProcessCreateSchema)
    @blp.response(201, BusinessProcessResponseSchema)
    @blp.doc(description="Create a new business process")
    @blp.alt_response(400, schema=ErrorSchema, description="Invalid request")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def post(self, process_data):
        """Create a new business process"""
        db_api = get_db_api()

        # Get or create business process type
        type_id = process_data.get('type_id')
        if not type_id:
            # Create default type if not provided
            type_id = db_api.bp_api.find_or_create_bp_type("Default Process Type")

        # Create business process
        bp_id = process_data.get('id', process_data['name'])
        bp_name = process_data['name']

        result = db_api.bp_api.create_business_process(bp_id, bp_name, type_id)

        if result:
            # Get the created process
            created_process = db_api.bp_api.find_bp_data_by_id(bp_id)
            if created_process and created_process.get('instances'):
                instance = created_process['instances'][0]
                return {
                    'success': True,
                    'message': 'Business process created successfully',
                    'data': instance,
                    'process_id': instance.get('id')
                }

        abort(500, message="Failed to create business process")


@blp.route('/<int:process_id>')
class BusinessProcessDetail(MethodView):
    """Business process detail, update, and delete endpoints"""

    @blp.response(200, BusinessProcessDetailSchema)
    @blp.doc(description="Get business process details by ID")
    @blp.alt_response(404, schema=ErrorSchema, description="Business process not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def get(self, process_id):
        """Get business process by ID"""
        db_api = get_db_api()

        process = db_api.bp_api.get_business_process(process_id)

        if not process:
            abort(404, message=f"Business process {process_id} not found")

        attrs = process.get('attributes', {})

        # Build detailed response
        response = {
            'process_id': process.get('id'),
            'name': attrs.get('name'),
            'description': attrs.get('description', ''),
            'process_type': 'Customized' if attrs.get('customized', False) else 'Typical',
            'org_unit': '',
            'customized': attrs.get('customized', False),
            'elements': [],
            'resources': [],
            'documents': []
        }

        # Get sub-elements
        elements = attrs.get('elements', [])
        for elem in elements:
            elem_id = elem.get('id') if isinstance(elem, dict) else elem
            if elem_id:
                elem_data = db_api.bp_api.get_business_process(elem_id)
                if elem_data:
                    elem_attrs = elem_data.get('attributes', {})
                    response['elements'].append({
                        'process_id': elem_id,
                        'name': elem_attrs.get('name'),
                        'description': elem_attrs.get('description', ''),
                        'process_type': 'Customized' if elem_attrs.get('customized', False) else 'Typical',
                        'org_unit': '',
                        'customized': elem_attrs.get('customized', False)
                    })

        # Get resources
        resources = attrs.get('resources', [])
        for res in resources:
            res_id = res.get('id') if isinstance(res, dict) else res
            if res_id:
                # Fetch resource details if needed
                response['resources'].append({
                    'id': res_id,
                    'type': res.get('type') if isinstance(res, dict) else 'apl_business_process_resource'
                })

        return response

    @blp.arguments(BusinessProcessUpdateSchema)
    @blp.response(200, BusinessProcessResponseSchema)
    @blp.doc(description="Update business process")
    @blp.alt_response(404, schema=ErrorSchema, description="Business process not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def put(self, update_data, process_id):
        """Update business process"""
        db_api = get_db_api()

        # Check if process exists
        existing = db_api.bp_api.get_business_process(process_id)
        if not existing:
            abort(404, message=f"Business process {process_id} not found")

        # Update process
        result = db_api.bp_api.update_business_process(process_id, update_data)

        if result:
            return {
                'success': True,
                'message': 'Business process updated successfully',
                'data': result,
                'process_id': process_id
            }

        abort(500, message="Failed to update business process")

    @blp.response(204)
    @blp.doc(description="Delete business process")
    @blp.alt_response(404, schema=ErrorSchema, description="Business process not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def delete(self, process_id):
        """Delete business process"""
        db_api = get_db_api()

        # Check if process exists
        existing = db_api.bp_api.get_business_process(process_id)
        if not existing:
            abort(404, message=f"Business process {process_id} not found")

        # Delete process (soft delete by default)
        success = db_api.bp_api.delete_business_process(process_id, soft_delete=True)

        if not success:
            abort(500, message="Failed to delete business process")

        return '', 204


@blp.route('/<int:process_id>/elements')
class BusinessProcessElements(MethodView):
    """Business process elements (sub-processes) management"""

    @blp.arguments(BusinessProcessElementCreateSchema)
    @blp.response(201, BusinessProcessResponseSchema)
    @blp.doc(description="Add a sub-process element to a business process")
    @blp.alt_response(404, schema=ErrorSchema, description="Business process not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def post(self, element_data, process_id):
        """Add element to business process"""
        db_api = get_db_api()

        element_id = element_data['element_id']

        # Verify both processes exist
        parent = db_api.bp_api.get_business_process(process_id)
        if not parent:
            abort(404, message=f"Parent business process {process_id} not found")

        child = db_api.bp_api.get_business_process(element_id)
        if not child:
            abort(404, message=f"Element business process {element_id} not found")

        # Add element
        result = db_api.bp_api.add_element_to_process(process_id, element_id)

        if result:
            return {
                'success': True,
                'message': 'Element added to business process successfully',
                'data': result,
                'process_id': process_id
            }

        abort(500, message="Failed to add element to business process")


@blp.route('/<int:process_id>/elements/<int:element_id>')
class BusinessProcessElementDetail(MethodView):
    """Business process element deletion"""

    @blp.response(204)
    @blp.doc(description="Remove an element from a business process")
    @blp.alt_response(404, schema=ErrorSchema, description="Business process not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def delete(self, process_id, element_id):
        """Remove element from business process"""
        db_api = get_db_api()

        # Verify parent exists
        parent = db_api.bp_api.get_business_process(process_id)
        if not parent:
            abort(404, message=f"Business process {process_id} not found")

        # Remove element
        result = db_api.bp_api.remove_element_from_process(process_id, element_id)

        if not result:
            abort(500, message="Failed to remove element from business process")

        return '', 204


@blp.route('/<int:process_id>/resources')
class BusinessProcessResources(MethodView):
    """Business process resources management"""

    @blp.arguments(BusinessProcessResourceCreateSchema)
    @blp.response(201, BusinessProcessResponseSchema)
    @blp.doc(description="Add a resource to a business process")
    @blp.alt_response(404, schema=ErrorSchema, description="Business process not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def post(self, resource_data, process_id):
        """Add resource to business process"""
        db_api = get_db_api()

        # Verify process exists
        process = db_api.bp_api.get_business_process(process_id)
        if not process:
            abort(404, message=f"Business process {process_id} not found")

        # Create resource using resources API
        type_id = resource_data['type_id']
        object_id = resource_data.get('object_id')
        value = resource_data.get('value_component')
        unit_id = resource_data.get('unit_id')

        resource_id = db_api.resources_api.create_resource(
            process_id, type_id, object_id, value, unit_id
        )

        if resource_id:
            # Get updated process
            updated_process = db_api.bp_api.get_business_process(process_id)
            return {
                'success': True,
                'message': 'Resource added to business process successfully',
                'data': updated_process,
                'process_id': process_id
            }

        abort(500, message="Failed to add resource to business process")


@blp.route('/<int:process_id>/resources/<int:resource_id>')
class BusinessProcessResourceDetail(MethodView):
    """Business process resource update and deletion"""

    @blp.arguments(BusinessProcessResourceUpdateSchema)
    @blp.response(200, BusinessProcessResponseSchema)
    @blp.doc(description="Update a business process resource")
    @blp.alt_response(404, schema=ErrorSchema, description="Resource not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def put(self, update_data, process_id, resource_id):
        """Update business process resource"""
        db_api = get_db_api()

        # Update resource
        result = db_api.update_instance(resource_id, 'apl_business_process_resource', update_data)

        if result:
            # Get updated process
            updated_process = db_api.bp_api.get_business_process(process_id)
            return {
                'success': True,
                'message': 'Resource updated successfully',
                'data': updated_process,
                'process_id': process_id
            }

        abort(500, message="Failed to update resource")

    @blp.response(204)
    @blp.doc(description="Delete a business process resource")
    @blp.alt_response(404, schema=ErrorSchema, description="Resource not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def delete(self, process_id, resource_id):
        """Delete business process resource"""
        db_api = get_db_api()

        # Delete resource
        success = db_api.delete_instance(resource_id, 'apl_business_process_resource', soft_delete=True)

        if not success:
            abort(500, message="Failed to delete resource")

        return '', 204
