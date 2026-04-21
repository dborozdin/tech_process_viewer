"""
Products API routes using Flask-Smorest.
"""

from flask import request
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from ..schemas.product_schemas import (
    ProductSchema,
    ProductCreateSchema,
    ProductUpdateSchema,
    ProductListResponseSchema,
    ProductResponseSchema,
    ProductDetailSchema,
    ProductDefinitionFormationSchema,
    ProductDefinitionCreateSchema,
    ProductDefinitionUpdateSchema,
    ProductDefinitionResponseSchema,
    ProductDefinitionListResponseSchema,
    BOMStructureSchema,
    BOMItemSchema,
    BOMItemCreateSchema,
    BOMItemUpdateSchema,
    BOMResponseSchema
)
from ..schemas.common_schemas import ErrorSchema


blp = Blueprint(
    'products',
    __name__,
    url_prefix='/api/v1/products',
    description='Product management endpoints'
)


def get_db_api():
    """Get DatabaseAPI instance from Flask app context"""
    from tech_process_viewer.api.app_helpers import get_api
    api = get_api()
    if api is None or api.connect_data is None:
        abort(401, message="Not connected to database. Please connect first via /api/connect")
    return api


@blp.route('/')
class ProductList(MethodView):
    """Product list and creation endpoints"""

    @blp.response(200, ProductListResponseSchema)
    @blp.doc(description="Get list of products with optional filtering")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def get(self):
        """List all products"""
        db_api = get_db_api()

        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        name_filter = request.args.get('name', None)

        # Build filters
        filters = {}
        if name_filter:
            filters['name'] = name_filter

        # Query products
        products = db_api.products_api.list_products(
            filters=filters if filters else None,
            limit=per_page * page
        )

        # Paginate results
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_products = products[start_idx:end_idx]

        # Format response
        product_list = []
        for prod in paginated_products:
            attrs = prod.get('attributes', {})
            product_list.append({
                'product_id': prod.get('id'),
                'id': attrs.get('id'),
                'name': attrs.get('name'),
                'description': attrs.get('description', ''),
                'code': attrs.get('code'),
                'has_versions': False  # Will be set if we query versions
            })

        return {
            'products': product_list,
            'total': len(products),
            'page': page,
            'per_page': per_page
        }

    @blp.arguments(ProductCreateSchema)
    @blp.response(201, ProductResponseSchema)
    @blp.doc(description="Create a new product")
    @blp.alt_response(400, schema=ErrorSchema, description="Invalid request")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def post(self, product_data):
        """Create a new product"""
        db_api = get_db_api()

        # Use existing create_product method (creates product + definition)
        prd_id = product_data.get('id', product_data['name'])
        prd_name = product_data['name']
        prd_type = "discrete"  # Default type
        prd_source = "make"    # Default source

        result = db_api.products_api.create_product(prd_id, prd_name, prd_type, prd_source)

        if result:
            # Get the created product definition
            created_pdf = db_api.products_api.get_product_definition(result)
            if created_pdf:
                # Get the product from the definition
                of_product = created_pdf.get('attributes', {}).get('of_product', {})
                if isinstance(of_product, dict) and 'id' in of_product:
                    product_sys_id = of_product['id']
                    created_product = db_api.products_api.get_product(product_sys_id)

                    if created_product:
                        return {
                            'success': True,
                            'message': 'Product created successfully',
                            'data': created_product,
                            'product_id': product_sys_id
                        }

        abort(500, message="Failed to create product")


@blp.route('/<int:product_id>')
class ProductDetail(MethodView):
    """Product detail, update, and delete endpoints"""

    @blp.response(200, ProductDetailSchema)
    @blp.doc(description="Get product details by ID")
    @blp.alt_response(404, schema=ErrorSchema, description="Product not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def get(self, product_id):
        """Get product by ID"""
        db_api = get_db_api()

        product = db_api.products_api.get_product(product_id)

        if not product:
            abort(404, message=f"Product {product_id} not found")

        # Get product definitions (versions)
        definitions = db_api.products_api.list_product_definitions(product_id)

        return {
            'product': product,
            'definitions': definitions,
            'definition_count': len(definitions)
        }

    @blp.arguments(ProductUpdateSchema)
    @blp.response(200, ProductResponseSchema)
    @blp.doc(description="Update product")
    @blp.alt_response(404, schema=ErrorSchema, description="Product not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def put(self, update_data, product_id):
        """Update product"""
        db_api = get_db_api()

        # Check if product exists
        existing = db_api.products_api.get_product(product_id)
        if not existing:
            abort(404, message=f"Product {product_id} not found")

        # Update product
        result = db_api.products_api.update_product(product_id, update_data)

        if result:
            return {
                'success': True,
                'message': 'Product updated successfully',
                'data': result,
                'product_id': product_id
            }

        abort(500, message="Failed to update product")

    @blp.response(204)
    @blp.doc(description="Delete product")
    @blp.alt_response(404, schema=ErrorSchema, description="Product not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def delete(self, product_id):
        """Delete product"""
        db_api = get_db_api()

        # Check if product exists
        existing = db_api.products_api.get_product(product_id)
        if not existing:
            abort(404, message=f"Product {product_id} not found")

        # Delete product (soft delete by default)
        success = db_api.products_api.delete_product(product_id, soft_delete=True)

        if not success:
            abort(500, message="Failed to delete product")

        return '', 204


@blp.route('/<int:product_id>/versions')
class ProductVersionList(MethodView):
    """Product versions (definitions) management"""

    @blp.response(200, ProductDefinitionListResponseSchema)
    @blp.doc(description="Get all versions of a product")
    @blp.alt_response(404, schema=ErrorSchema, description="Product not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def get(self, product_id):
        """List product versions"""
        db_api = get_db_api()

        # Verify product exists
        product = db_api.products_api.get_product(product_id)
        if not product:
            abort(404, message=f"Product {product_id} not found")

        # Get all definitions
        definitions = db_api.products_api.list_product_definitions(product_id)

        return {
            'product_id': product_id,
            'definitions': definitions,
            'total': len(definitions)
        }

    @blp.arguments(ProductDefinitionCreateSchema)
    @blp.response(201, ProductDefinitionResponseSchema)
    @blp.doc(description="Create a new product version")
    @blp.alt_response(404, schema=ErrorSchema, description="Product not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def post(self, definition_data, product_id):
        """Create product version"""
        db_api = get_db_api()

        # Verify product exists
        product = db_api.products_api.get_product(product_id)
        if not product:
            abort(404, message=f"Product {product_id} not found")

        # Create definition
        result = db_api.products_api.create_product_definition(product_id, definition_data)

        if result:
            return {
                'success': True,
                'message': 'Product version created successfully',
                'data': result,
                'definition_id': result.get('id')
            }

        abort(500, message="Failed to create product version")


@blp.route('/<int:product_id>/versions/<int:version_id>')
class ProductVersionDetail(MethodView):
    """Product version detail operations"""

    @blp.response(200, ProductDefinitionFormationSchema)
    @blp.doc(description="Get product version details")
    @blp.alt_response(404, schema=ErrorSchema, description="Version not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def get(self, product_id, version_id):
        """Get product version"""
        db_api = get_db_api()

        version = db_api.products_api.get_product_definition(version_id)

        if not version:
            abort(404, message=f"Product version {version_id} not found")

        return version

    @blp.arguments(ProductDefinitionUpdateSchema)
    @blp.response(200, ProductDefinitionResponseSchema)
    @blp.doc(description="Update product version")
    @blp.alt_response(404, schema=ErrorSchema, description="Version not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def put(self, update_data, product_id, version_id):
        """Update product version"""
        db_api = get_db_api()

        # Check if version exists
        existing = db_api.products_api.get_product_definition(version_id)
        if not existing:
            abort(404, message=f"Product version {version_id} not found")

        # Update version
        result = db_api.products_api.update_product_definition(version_id, update_data)

        if result:
            return {
                'success': True,
                'message': 'Product version updated successfully',
                'data': result,
                'definition_id': version_id
            }

        abort(500, message="Failed to update product version")

    @blp.response(204)
    @blp.doc(description="Delete product version")
    @blp.alt_response(404, schema=ErrorSchema, description="Version not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def delete(self, product_id, version_id):
        """Delete product version"""
        db_api = get_db_api()

        # Check if version exists
        existing = db_api.products_api.get_product_definition(version_id)
        if not existing:
            abort(404, message=f"Product version {version_id} not found")

        # Delete version
        success = db_api.products_api.delete_product_definition(version_id, soft_delete=True)

        if not success:
            abort(500, message="Failed to delete product version")

        return '', 204


@blp.route('/<int:product_id>/bom')
class ProductBOM(MethodView):
    """Product BOM (Bill of Materials) management"""

    @blp.response(200, BOMStructureSchema)
    @blp.doc(description="Get BOM structure for a product")
    @blp.alt_response(404, schema=ErrorSchema, description="Product not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def get(self, product_id):
        """Get product BOM structure"""
        db_api = get_db_api()

        # Get product and its first definition
        product = db_api.products_api.get_product(product_id)
        if not product:
            abort(404, message=f"Product {product_id} not found")

        definitions = db_api.products_api.list_product_definitions(product_id)
        if not definitions:
            return {
                'product_definition_id': None,
                'product_name': product.get('attributes', {}).get('name'),
                'components': [],
                'total_components': 0
            }

        # Use first definition
        pdf_id = definitions[0].get('id')
        components = db_api.products_api.get_bom_structure(pdf_id)

        return {
            'product_definition_id': pdf_id,
            'product_name': product.get('attributes', {}).get('name'),
            'components': components,
            'total_components': len(components)
        }


@blp.route('/<int:product_id>/bom/items')
class ProductBOMItems(MethodView):
    """Add components to product BOM"""

    @blp.arguments(BOMItemCreateSchema)
    @blp.response(201, BOMResponseSchema)
    @blp.doc(description="Add a component to product BOM")
    @blp.alt_response(404, schema=ErrorSchema, description="Product not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def post(self, bom_data, product_id):
        """Add component to BOM"""
        db_api = get_db_api()

        # Get product definition
        definitions = db_api.products_api.list_product_definitions(product_id)
        if not definitions:
            abort(404, message=f"Product {product_id} has no definitions")

        parent_pdf_id = definitions[0].get('id')
        component_pdf_id = bom_data['component_id']
        quantity = bom_data['quantity']
        unit_id = bom_data.get('unit_id', 1)

        # Add component
        bom_item_id = db_api.products_api.add_component_to_bom(
            parent_pdf_id=parent_pdf_id,
            component_pdf_id=component_pdf_id,
            quantity=quantity,
            unit_id=unit_id,
            reference_designator=bom_data.get('reference_designator')
        )
        # add_component_to_bom may return (sys_id, "created"/"found") tuple — unwrap.
        if isinstance(bom_item_id, tuple):
            bom_item_id = bom_item_id[0]

        if bom_item_id:
            bom_item = db_api.products_api.get_bom_item(bom_item_id)
            return {
                'success': True,
                'message': 'Component added to BOM successfully',
                'data': bom_item,
                'bom_item_id': bom_item_id
            }

        abort(500, message="Failed to add component to BOM")


@blp.route('/<int:product_id>/bom/items/<int:bom_item_id>')
class ProductBOMItemDetail(MethodView):
    """BOM item operations"""

    @blp.arguments(BOMItemUpdateSchema)
    @blp.response(200, BOMResponseSchema)
    @blp.doc(description="Update BOM item")
    @blp.alt_response(404, schema=ErrorSchema, description="BOM item not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def put(self, update_data, product_id, bom_item_id):
        """Update BOM item"""
        db_api = get_db_api()

        # Check if BOM item exists
        existing = db_api.products_api.get_bom_item(bom_item_id)
        if not existing:
            abort(404, message=f"BOM item {bom_item_id} not found")

        # Prepare updates
        updates = {}
        if 'quantity' in update_data:
            updates['value_component'] = update_data['quantity']
        if 'unit_id' in update_data:
            updates['unit_component'] = {"id": update_data['unit_id'], "type": "apl_unit"}
        if 'reference_designator' in update_data:
            updates['reference_designator'] = update_data['reference_designator']

        # Update BOM item
        result = db_api.products_api.update_bom_item(bom_item_id, updates)

        if result:
            return {
                'success': True,
                'message': 'BOM item updated successfully',
                'data': result,
                'bom_item_id': bom_item_id
            }

        abort(500, message="Failed to update BOM item")

    @blp.response(204)
    @blp.doc(description="Delete BOM item")
    @blp.alt_response(404, schema=ErrorSchema, description="BOM item not found")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def delete(self, product_id, bom_item_id):
        """Delete BOM item"""
        db_api = get_db_api()

        # Check if BOM item exists
        existing = db_api.products_api.get_bom_item(bom_item_id)
        if not existing:
            abort(404, message=f"BOM item {bom_item_id} not found")

        # Delete BOM item
        success = db_api.products_api.delete_bom_item(bom_item_id, soft_delete=True)

        if not success:
            abort(500, message="Failed to delete BOM item")

        return '', 204
