"""
Organizations API routes using Flask-Smorest.
"""

from flask import request
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from ..schemas.resource_schemas import (
    OrganizationSchema,
    OrganizationCreateSchema,
    OrganizationUpdateSchema,
    OrganizationDetailSchema,
    OrganizationListResponseSchema,
    OrganizationResponseSchema
)
from ..schemas.common_schemas import ErrorSchema


blp = Blueprint(
    'organizations',
    __name__,
    url_prefix='/api/v1/organizations',
    description='Organization management endpoints'
)


def get_db_api():
    """Get DatabaseAPI instance from Flask app context"""
    from tech_process_viewer.api.app_helpers import get_api
    api = get_api()
    if api is None or api.connect_data is None:
        abort(401, message="Not connected to database. Please connect first via /api/connect")
    return api


@blp.route('/')
class OrganizationList(MethodView):
    """Organization list and creation endpoints"""

    @blp.response(200, OrganizationListResponseSchema)
    @blp.doc(description="Get list of organizations with optional filtering")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def get(self):
        """List all organizations"""
        db_api = get_db_api()

        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        name_filter = request.args.get('name', None)

        # Build filters
        filters = {}
        if name_filter:
            filters['name'] = name_filter

        # Query organizations
        organizations = db_api.org_api.list_organizations(
            filters=filters if filters else None,
            limit=per_page * page
        )

        # Paginate results
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_orgs = organizations[start_idx:end_idx]

        # Format response
        org_list = []
        for org in paginated_orgs:
            attrs = org.get('attributes', {})
            org_list.append({
                'organization_id': org.get('id'),
                'id': attrs.get('id'),
                'name': attrs.get('name'),
                'description': attrs.get('description')
            })

        return {
            'organizations': org_list,
            'total': len(organizations),
            'page': page,
            'per_page': per_page
        }

    @blp.arguments(OrganizationCreateSchema)
    @blp.response(201, OrganizationResponseSchema)
    @blp.doc(description="Create a new organization")
    @blp.alt_response(400, schema=ErrorSchema, description="Invalid request")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def post(self, organization_data):
        """Create a new organization"""
        db_api = get_db_api()

        # Build attributes
        attributes = {
            'id': organization_data['id'],
            'name': organization_data['name']
        }

        if 'description' in organization_data:
            attributes['description'] = organization_data['description']

        # Create organization
        result = db_api.create_instance('organization', attributes)

        if result:
            created_org = db_api.org_api.get_organization(result)
            if created_org:
                return {
                    'success': True,
                    'message': 'Organization created successfully',
                    'data': created_org,
                    'organization_id': result
                }

        abort(500, message="Failed to create organization")


@blp.route('/<int:organization_id>')
class OrganizationDetail(MethodView):
    """Organization detail, update, and delete endpoints"""

    @blp.response(200, OrganizationDetailSchema)
    @blp.doc(description="Get organization details by ID")
    @blp.alt_response(404, schema=ErrorSchema, description="Organization not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def get(self, organization_id):
        """Get organization by ID"""
        db_api = get_db_api()

        organization = db_api.org_api.get_organization(organization_id)

        if not organization:
            abort(404, message=f"Organization {organization_id} not found")

        return organization

    @blp.arguments(OrganizationUpdateSchema)
    @blp.response(200, OrganizationResponseSchema)
    @blp.doc(description="Update organization")
    @blp.alt_response(404, schema=ErrorSchema, description="Organization not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def put(self, update_data, organization_id):
        """Update organization"""
        db_api = get_db_api()

        # Check if organization exists
        existing = db_api.org_api.get_organization(organization_id)
        if not existing:
            abort(404, message=f"Organization {organization_id} not found")

        # Update organization
        result = db_api.org_api.update_organization(organization_id, update_data)

        if result:
            return {
                'success': True,
                'message': 'Organization updated successfully',
                'data': result,
                'organization_id': organization_id
            }

        abort(500, message="Failed to update organization")

    @blp.response(204)
    @blp.doc(description="Delete organization")
    @blp.alt_response(404, schema=ErrorSchema, description="Organization not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def delete(self, organization_id):
        """Delete organization"""
        db_api = get_db_api()

        # Check if organization exists
        existing = db_api.org_api.get_organization(organization_id)
        if not existing:
            abort(404, message=f"Organization {organization_id} not found")

        # Delete organization (soft delete by default)
        success = db_api.org_api.delete_organization(organization_id, soft_delete=True)

        if not success:
            abort(500, message="Failed to delete organization")

        return '', 204
