"""
Resources API routes using Flask-Smorest.
"""

from flask import request
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from ..schemas.resource_schemas import (
    ResourceSchema,
    ResourceCreateSchema,
    ResourceUpdateSchema,
    ResourceDetailSchema,
    ResourceListResponseSchema,
    ResourceResponseSchema,
    ResourceTypeListResponseSchema
)
from ..schemas.common_schemas import ErrorSchema


blp = Blueprint(
    'resources',
    __name__,
    url_prefix='/api/v1/resources',
    description='Resource management endpoints'
)


def get_db_api():
    """Get DatabaseAPI instance from Flask app context"""
    from tech_process_viewer.api.app_helpers import get_api
    api = get_api()
    if api is None or api.connect_data is None:
        abort(401, message="Not connected to database. Please connect first via /api/connect")
    return api


@blp.route('/')
class ResourceList(MethodView):
    """Resource list and creation endpoints"""

    @blp.response(200, ResourceListResponseSchema)
    @blp.doc(description="Get list of resources with optional filtering")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def get(self):
        """List all resources"""
        db_api = get_db_api()

        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        process_id = request.args.get('process_id', None, type=int)

        # Build filters
        filters = {}
        if process_id:
            filters['process_id'] = process_id

        # Query resources
        resources = db_api.resources_api.list_resources(
            filters=filters if filters else None,
            limit=per_page * page
        )

        # Paginate results
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_resources = resources[start_idx:end_idx]

        # Format response
        resource_list = []
        for res in paginated_resources:
            attrs = res.get('attributes', {})

            # Resolve type name
            type_obj = attrs.get('type', {})
            type_name = None
            if isinstance(type_obj, dict) and 'id' in type_obj:
                type_instance = db_api.get_instance(type_obj['id'])
                if type_instance:
                    type_name = type_instance.get('attributes', {}).get('name')

            # Resolve unit name
            unit_obj = attrs.get('unit_component', {})
            unit_name = None
            if isinstance(unit_obj, dict) and 'id' in unit_obj:
                unit_instance = db_api.get_instance(unit_obj['id'])
                if unit_instance:
                    unit_name = unit_instance.get('attributes', {}).get('name')

            # Extract process ID
            process_obj = attrs.get('process', {})
            proc_id = process_obj.get('id') if isinstance(process_obj, dict) else None

            resource_list.append({
                'resource_id': res.get('id'),
                'process_id': proc_id,
                'type_name': type_name,
                'value_component': attrs.get('value_component'),
                'unit_name': unit_name
            })

        return {
            'resources': resource_list,
            'total': len(resources),
            'page': page,
            'per_page': per_page
        }

    @blp.arguments(ResourceCreateSchema)
    @blp.response(201, ResourceResponseSchema)
    @blp.doc(description="Create a new resource")
    @blp.alt_response(400, schema=ErrorSchema, description="Invalid request")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def post(self, resource_data):
        """Create a new resource"""
        db_api = get_db_api()

        process_id = resource_data['process_id']
        type_id = resource_data['type_id']
        object_id = resource_data.get('object_id')
        value_component = resource_data.get('value_component')
        unit_id = resource_data.get('unit_id')

        # Build attributes
        attributes = {
            'process': {
                'id': process_id,
                'type': 'apl_business_process'
            },
            'type': {
                'id': type_id,
                'type': 'apl_business_process_resource_type'
            }
        }

        if value_component is not None:
            attributes['value_component'] = value_component

        if unit_id is not None:
            attributes['unit_component'] = {
                'id': unit_id,
                'type': 'apl_unit'
            }

        if object_id is not None:
            # Default object type - could be parameterized
            attributes['object'] = {
                'id': object_id,
                'type': 'apl_product_definition_formation'
            }

        # Create resource
        result = db_api.create_instance('apl_business_process_resource', attributes)

        if result:
            created_resource = db_api.resources_api.get_resource(result)
            if created_resource:
                return {
                    'success': True,
                    'message': 'Resource created successfully',
                    'data': created_resource,
                    'resource_id': result
                }

        abort(500, message="Failed to create resource")


@blp.route('/<int:resource_id>')
class ResourceDetail(MethodView):
    """Resource detail, update, and delete endpoints"""

    @blp.response(200, ResourceDetailSchema)
    @blp.doc(description="Get resource details by ID")
    @blp.alt_response(404, schema=ErrorSchema, description="Resource not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def get(self, resource_id):
        """Get resource by ID"""
        db_api = get_db_api()

        resource = db_api.resources_api.get_resource(resource_id)

        if not resource:
            abort(404, message=f"Resource {resource_id} not found")

        return resource

    @blp.arguments(ResourceUpdateSchema)
    @blp.response(200, ResourceResponseSchema)
    @blp.doc(description="Update resource")
    @blp.alt_response(404, schema=ErrorSchema, description="Resource not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def put(self, update_data, resource_id):
        """Update resource"""
        db_api = get_db_api()

        # Check if resource exists
        existing = db_api.resources_api.get_resource(resource_id)
        if not existing:
            abort(404, message=f"Resource {resource_id} not found")

        # Update resource
        result = db_api.resources_api.update_resource(resource_id, update_data)

        if result:
            return {
                'success': True,
                'message': 'Resource updated successfully',
                'data': result,
                'resource_id': resource_id
            }

        abort(500, message="Failed to update resource")

    @blp.response(204)
    @blp.doc(description="Delete resource")
    @blp.alt_response(404, schema=ErrorSchema, description="Resource not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def delete(self, resource_id):
        """Delete resource"""
        db_api = get_db_api()

        # Check if resource exists
        existing = db_api.resources_api.get_resource(resource_id)
        if not existing:
            abort(404, message=f"Resource {resource_id} not found")

        # Delete resource (soft delete by default)
        success = db_api.resources_api.delete_resource(resource_id, soft_delete=True)

        if not success:
            abort(500, message="Failed to delete resource")

        return '', 204


@blp.route('/types')
class ResourceTypeList(MethodView):
    """Resource types list endpoint"""

    @blp.response(200, ResourceTypeListResponseSchema)
    @blp.doc(description="Get list of resource types")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def get(self):
        """List all resource types"""
        db_api = get_db_api()

        # Get all resource types
        types = db_api.resources_api.list_resource_types(limit=1000)

        # Format response
        type_list = []
        for type_inst in types:
            attrs = type_inst.get('attributes', {})
            type_list.append({
                'id': attrs.get('id'),
                'name': attrs.get('name'),
                'description': attrs.get('description')
            })

        return {
            'resource_types': type_list,
            'total': len(type_list)
        }
