"""CRUD routes for Tech Process Viewer.

Simple Flask Blueprint (no flask-smorest) providing write operations
for products, business processes, documents, characteristics, and resources.
"""

import json
import os
import tempfile
import requests as http_requests
from flask import Blueprint, request, jsonify
from tech_process_viewer.api.app_helpers import get_api
from tech_process_viewer.globals import logger

crud_blp = Blueprint('crud', __name__)


def _get_api_or_error():
    api = get_api()
    if api is None or api.connect_data is None:
        return None, (jsonify({'success': False, 'message': 'Not connected to DB'}), 401)
    return api, None


# ========== Products ==========

@crud_blp.route('/api/products', methods=['POST'])
def create_product():
    api, err = _get_api_or_error()
    if err:
        return err

    data = request.get_json()
    prd_id = data.get('id', '')
    prd_name = data.get('name', '')
    prd_type = data.get('type', 'make')
    prd_source = data.get('source', 'make')

    try:
        result = api.products_api.create_product(prd_id, prd_name, prd_type, prd_source)
        if result is None:
            return jsonify({'success': False, 'message': 'Failed to create product'}), 500

        pdf_id = result  # sys_id of apl_product_definition_formation

        # Add to Aircrafts folder (append to existing content, not replace)
        folder_data = api.folders_api.find_folder("Aircrafts")
        if folder_data:
            folder_id = folder_data[0]
            # Load existing content and append
            existing_ids = api.folders_api.get_folder_content(folder_id) or []
            existing_ids.append(pdf_id)
            # Build content array with all items
            content = [{"id": cid, "type": "apl_product_definition_formation"} for cid in existing_ids]
            payload = {
                "format": "apl_json_1",
                "dictionary": "apl_pss_a",
                "instances": [{
                    "id": folder_id,
                    "type": "apl_folder",
                    "attributes": {"content": content}
                }]
            }
            http_requests.post(
                url=api.URL_QUERY_SAVE,
                headers={"X-APL-SessionKey": api.connect_data['session_key']},
                json=payload
            )

        return jsonify({'success': True, 'message': 'Product created', 'data': {'pdf_id': pdf_id}}), 201
    except Exception as e:
        logger.error(f"Error creating product: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@crud_blp.route('/api/products/<int:pdf_id>', methods=['PUT'])
def update_product(pdf_id):
    api, err = _get_api_or_error()
    if err:
        return err

    data = request.get_json()

    try:
        # pdf_id is the apl_product_definition_formation sys_id
        # Get the product sys_id from the PDF
        pdf_instance = api.products_api.get_product_definition(pdf_id)
        if not pdf_instance:
            return jsonify({'success': False, 'message': 'Product definition not found'}), 404

        of_product = pdf_instance.get('attributes', {}).get('of_product', {})
        product_sys_id = of_product.get('id') if isinstance(of_product, dict) else None

        if product_sys_id:
            product_updates = {}
            if 'name' in data:
                product_updates['name'] = data['name']
            if 'id' in data:
                product_updates['id'] = data['id']
            if product_updates:
                api.products_api.update_product(product_sys_id, product_updates)

        return jsonify({'success': True, 'message': 'Product updated'})
    except Exception as e:
        logger.error(f"Error updating product: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@crud_blp.route('/api/products/<int:pdf_id>', methods=['DELETE'])
def delete_product(pdf_id):
    api, err = _get_api_or_error()
    if err:
        return err

    try:
        # Remove from Aircrafts folder first
        folder_data = api.folders_api.find_folder("Aircrafts")
        if folder_data:
            folder_id = folder_data[0]
            api.folders_api.remove_item_from_folder(folder_id, pdf_id)

        # Delete the PDF
        api.products_api.delete_product_definition(pdf_id)

        return jsonify({'success': True, 'message': 'Product deleted'})
    except Exception as e:
        logger.error(f"Error deleting product: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ========== BOM (Product Assembly) ==========

@crud_blp.route('/api/products/bom', methods=['POST'])
def create_bom_link():
    api, err = _get_api_or_error()
    if err:
        return err

    data = request.get_json()
    relating_pdf_id = data.get('relating_pdf_id')  # parent
    related_pdf_id = data.get('related_pdf_id')    # child/component
    quantity = data.get('quantity', 1)
    unit_id = data.get('unit_id')

    if not relating_pdf_id or not related_pdf_id:
        return jsonify({'success': False, 'message': 'relating_pdf_id and related_pdf_id are required'}), 400

    try:
        # Find or create unit if not provided
        if not unit_id:
            unit_id = api.units_api.find_unit_by_id("EA")
            if not unit_id:
                unit_id = api.units_api.find_unit_by_id("шт")

        result = api.products_api.create_product_assembly(
            pdf_related=related_pdf_id,
            pdf_relating=relating_pdf_id,
            quantity=quantity,
            UOM=unit_id or 0
        )

        if result:
            bom_id = result[0] if isinstance(result, tuple) else result
            return jsonify({'success': True, 'message': 'BOM link created', 'data': {'bom_id': bom_id}}), 201
        return jsonify({'success': False, 'message': 'Failed to create BOM link'}), 500
    except Exception as e:
        logger.error(f"Error creating BOM link: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@crud_blp.route('/api/products/bom/<int:bom_id>', methods=['DELETE'])
def delete_bom_link(bom_id):
    api, err = _get_api_or_error()
    if err:
        return err

    try:
        success = api.products_api.delete_bom_item(bom_id)
        if success:
            return jsonify({'success': True, 'message': 'BOM link deleted'})
        return jsonify({'success': False, 'message': 'Failed to delete BOM link'}), 500
    except Exception as e:
        logger.error(f"Error deleting BOM link: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@crud_blp.route('/api/products/<int:pdf_id>/bom', methods=['GET'])
def get_bom(pdf_id):
    api, err = _get_api_or_error()
    if err:
        return err

    try:
        bom = api.products_api.get_bom_structure(pdf_id)
        return jsonify({'success': True, 'data': bom})
    except Exception as e:
        logger.error(f"Error getting BOM: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ========== Business Processes ==========

@crud_blp.route('/api/business-processes', methods=['POST'])
def create_business_process():
    api, err = _get_api_or_error()
    if err:
        return err

    data = request.get_json()
    bp_name = data.get('name', '')
    bp_id = data.get('id', bp_name)
    bp_description = data.get('description', '')

    try:
        # Find or create BP type
        type_name = data.get('type_name', 'Default')
        type_id = api.bp_api.find_or_create_bp_type(type_name)

        result = api.bp_api.create_business_process(bp_id, bp_name, type_id)
        if result:
            bp_sys_id = result[0] if isinstance(result, tuple) else result
            bp_version_id = result[1] if isinstance(result, tuple) and len(result) > 1 else None

            # Set description if provided
            if bp_description:
                api.bp_api.update_business_process(bp_sys_id, {'description': bp_description})

            return jsonify({
                'success': True,
                'message': 'Business process created',
                'data': {'bp_id': bp_sys_id, 'version_id': bp_version_id}
            }), 201

        return jsonify({'success': False, 'message': 'Failed to create business process'}), 500
    except Exception as e:
        logger.error(f"Error creating business process: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@crud_blp.route('/api/business-processes/<int:bp_id>', methods=['PUT'])
def update_business_process(bp_id):
    api, err = _get_api_or_error()
    if err:
        return err

    data = request.get_json()
    updates = {}
    if 'name' in data:
        updates['name'] = data['name']
    if 'description' in data:
        updates['description'] = data['description']

    try:
        result = api.bp_api.update_business_process(bp_id, updates)
        if result:
            return jsonify({'success': True, 'message': 'Business process updated'})
        return jsonify({'success': False, 'message': 'Failed to update'}), 500
    except Exception as e:
        logger.error(f"Error updating BP: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@crud_blp.route('/api/business-processes/<int:bp_id>', methods=['DELETE'])
def delete_business_process(bp_id):
    api, err = _get_api_or_error()
    if err:
        return err

    try:
        success = api.bp_api.delete_business_process(bp_id)
        if success:
            return jsonify({'success': True, 'message': 'Business process deleted'})
        return jsonify({'success': False, 'message': 'Failed to delete'}), 500
    except Exception as e:
        logger.error(f"Error deleting BP: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@crud_blp.route('/api/business-processes/<int:bp_id>/elements', methods=['POST'])
def add_bp_element(bp_id):
    api, err = _get_api_or_error()
    if err:
        return err

    data = request.get_json()
    child_id = data.get('element_id')

    if not child_id:
        return jsonify({'success': False, 'message': 'element_id is required'}), 400

    try:
        result = api.bp_api.add_element_to_process(bp_id, child_id)
        if result:
            return jsonify({'success': True, 'message': 'Element added'}), 201
        return jsonify({'success': False, 'message': 'Failed to add element'}), 500
    except Exception as e:
        logger.error(f"Error adding BP element: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@crud_blp.route('/api/business-processes/<int:bp_id>/elements/<int:child_id>', methods=['DELETE'])
def remove_bp_element(bp_id, child_id):
    api, err = _get_api_or_error()
    if err:
        return err

    try:
        result = api.bp_api.remove_element_from_process(bp_id, child_id)
        if result:
            return jsonify({'success': True, 'message': 'Element removed'})
        return jsonify({'success': False, 'message': 'Failed to remove element'}), 500
    except Exception as e:
        logger.error(f"Error removing BP element: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@crud_blp.route('/api/business-processes/<int:bp_id>/link-product', methods=['POST'])
def link_bp_to_product(bp_id):
    api, err = _get_api_or_error()
    if err:
        return err

    data = request.get_json()
    pdf_id = data.get('pdf_id')

    if not pdf_id:
        return jsonify({'success': False, 'message': 'pdf_id is required'}), 400

    try:
        ref_id = api.bp_api.find_or_create_bp_reference(bp=bp_id, pdf=pdf_id)
        if ref_id:
            return jsonify({'success': True, 'message': 'BP linked to product', 'data': {'ref_id': ref_id}}), 201
        return jsonify({'success': False, 'message': 'Failed to link'}), 500
    except Exception as e:
        logger.error(f"Error linking BP to product: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ========== Documents ==========

@crud_blp.route('/api/documents/upload', methods=['POST'])
def upload_document():
    """Upload file from disk, create apl_document + blob + reference."""
    api, err = _get_api_or_error()
    if err:
        return err

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided'}), 400

    file = request.files['file']
    doc_id = request.form.get('doc_id', file.filename)
    doc_name = request.form.get('doc_name', file.filename)
    doc_type_id = request.form.get('doc_type_id')
    item_id = request.form.get('item_id')
    item_type = request.form.get('item_type', 'apl_business_process')

    try:
        # Save file to temp location
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, file.filename)
        file.save(temp_path)

        try:
            # Find or create document type
            if not doc_type_id:
                doc_type_id = api.docs_api.find_or_create_doc_type("DEFAULT", "Default")

            # Create document with blob upload
            result = api.docs_api.create_document(
                doc_id=doc_id,
                doc_name=doc_name,
                doc_type=doc_type_id,
                crc=None,
                src_date=None,
                stored_doc_id=None,
                file_path=temp_path
            )

            if result is None:
                return jsonify({'success': False, 'message': 'Failed to create document'}), 500

            doc_sys_id = result[0] if isinstance(result, tuple) else result

            # Create document reference if item_id provided
            ref_id = None
            if item_id:
                ref_result = api.docs_api.create_document_reference(
                    doc=doc_sys_id,
                    ref_object=int(item_id),
                    ref_object_type=item_type
                )
                if ref_result:
                    ref_id = ref_result[0] if isinstance(ref_result, tuple) else ref_result

            return jsonify({
                'success': True,
                'message': 'Document uploaded',
                'data': {'doc_id': doc_sys_id, 'ref_id': ref_id}
            }), 201

        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)

    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@crud_blp.route('/api/document-references', methods=['POST'])
def create_document_reference():
    api, err = _get_api_or_error()
    if err:
        return err

    data = request.get_json()
    doc_id = data.get('doc_id')
    item_id = data.get('item_id')
    item_type = data.get('item_type', 'apl_business_process')

    if not doc_id or not item_id:
        return jsonify({'success': False, 'message': 'doc_id and item_id are required'}), 400

    try:
        result = api.docs_api.create_document_reference(
            doc=doc_id, ref_object=item_id, ref_object_type=item_type
        )
        if result:
            ref_id = result[0] if isinstance(result, tuple) else result
            return jsonify({'success': True, 'message': 'Document reference created', 'data': {'ref_id': ref_id}}), 201
        return jsonify({'success': False, 'message': 'Failed to create reference'}), 500
    except Exception as e:
        logger.error(f"Error creating doc reference: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@crud_blp.route('/api/document-references/<int:ref_id>', methods=['DELETE'])
def delete_document_reference(ref_id):
    api, err = _get_api_or_error()
    if err:
        return err

    try:
        success = api.docs_api.delete_document_reference(ref_id)
        if success:
            return jsonify({'success': True, 'message': 'Document reference deleted'})
        return jsonify({'success': False, 'message': 'Failed to delete reference'}), 500
    except Exception as e:
        logger.error(f"Error deleting doc reference: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@crud_blp.route('/api/documents/search', methods=['GET'])
def search_documents():
    api, err = _get_api_or_error()
    if err:
        return err

    q = request.args.get('q', '')

    try:
        # Search by document id (code)
        results = []
        if q:
            query = f'SELECT NO_CASE Ext_ FROM Ext_{{apl_document(.id LIKE "{q}")}} END_SELECT'
            data = api.query_apl(query)
            if data and 'instances' in data:
                for inst in data['instances'][:20]:
                    attrs = inst.get('attributes', {})
                    results.append({
                        'sys_id': inst.get('id'),
                        'doc_id': attrs.get('id', ''),
                        'name': attrs.get('name', ''),
                        'type': inst.get('type', '')
                    })

        return jsonify({'success': True, 'data': results})
    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ========== Characteristics ==========

@crud_blp.route('/api/characteristics', methods=['GET'])
def list_characteristics():
    api, err = _get_api_or_error()
    if err:
        return err

    try:
        chars = api.characteristic_api.list_characteristics()
        result = []
        for ch in chars:
            attrs = ch.get('attributes', {})
            result.append({
                'sys_id': ch.get('id'),
                'name': attrs.get('name', ''),
                'description': attrs.get('description', ''),
                'id': attrs.get('id', '')
            })
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        logger.error(f"Error listing characteristics: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@crud_blp.route('/api/characteristics/values/<int:item_id>', methods=['GET'])
def get_characteristic_values(item_id):
    api, err = _get_api_or_error()
    if err:
        return err

    try:
        values = api.characteristic_api.get_values_for_item(item_id)
        result = []
        for val in values:
            attrs = val.get('attributes', {})
            char_ref = attrs.get('characteristic', {})
            char_name = ''
            if isinstance(char_ref, dict) and 'id' in char_ref:
                char_inst = api.characteristic_api.get_characteristic(char_ref['id'])
                if char_inst:
                    char_name = char_inst.get('attributes', {}).get('name', '')

            parsed = api.characteristic_api._extract_display_value(val)
            result.append({
                'sys_id': val.get('id'),
                'characteristic_name': char_name,
                'characteristic_id': char_ref.get('id') if isinstance(char_ref, dict) else None,
                'value': parsed.get('value', ''),
                'scope': parsed.get('scope', ''),
                'subtype': val.get('type', ''),
                'unit': parsed.get('unit', '')
            })
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        logger.error(f"Error getting characteristic values: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@crud_blp.route('/api/characteristics/values', methods=['POST'])
def create_characteristic_value():
    api, err = _get_api_or_error()
    if err:
        return err

    data = request.get_json()
    item_id = data.get('item_id')
    char_id = data.get('characteristic_id')
    value = data.get('value', '')
    subtype = data.get('subtype', 'apl_descriptive_characteristic_value')

    if not item_id or not char_id:
        return jsonify({'success': False, 'message': 'item_id and characteristic_id are required'}), 400

    try:
        result = api.characteristic_api.create_characteristic_value(item_id, char_id, value, subtype)
        if result:
            return jsonify({
                'success': True,
                'message': 'Characteristic value created',
                'data': {'sys_id': result.get('id') if isinstance(result, dict) else result}
            }), 201
        return jsonify({'success': False, 'message': 'Failed to create value'}), 500
    except Exception as e:
        logger.error(f"Error creating characteristic value: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@crud_blp.route('/api/characteristics/values/<int:value_id>', methods=['PUT'])
def update_characteristic_value(value_id):
    api, err = _get_api_or_error()
    if err:
        return err

    data = request.get_json()
    new_value = data.get('value', '')
    subtype = data.get('subtype', 'apl_descriptive_characteristic_value')

    try:
        result = api.characteristic_api.update_characteristic_value(value_id, new_value, subtype)
        if result:
            return jsonify({'success': True, 'message': 'Characteristic value updated'})
        return jsonify({'success': False, 'message': 'Failed to update'}), 500
    except Exception as e:
        logger.error(f"Error updating characteristic value: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@crud_blp.route('/api/characteristics/values/<int:value_id>', methods=['DELETE'])
def delete_characteristic_value(value_id):
    api, err = _get_api_or_error()
    if err:
        return err

    try:
        success = api.characteristic_api.delete_characteristic_value(value_id)
        if success:
            return jsonify({'success': True, 'message': 'Characteristic value deleted'})
        return jsonify({'success': False, 'message': 'Failed to delete'}), 500
    except Exception as e:
        logger.error(f"Error deleting characteristic value: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ========== Resources ==========

@crud_blp.route('/api/resources', methods=['POST'])
def create_resource():
    api, err = _get_api_or_error()
    if err:
        return err

    data = request.get_json()
    process_id = data.get('process_id')
    type_id = data.get('type_id')
    res_id = data.get('id', '')
    res_name = data.get('name', '')
    object_id = data.get('object_id', 0)
    object_type = data.get('object_type', 'organization')
    value = data.get('value_component', 0)
    unit_id = data.get('unit_id', 0)

    if not process_id or not type_id:
        return jsonify({'success': False, 'message': 'process_id and type_id are required'}), 400

    try:
        resource_id = api.resources_api.create_resource(
            res_id=res_id, res_name=res_name, res_type=type_id,
            bp=process_id, item=object_id, item_type=object_type,
            value=value, unit=unit_id
        )
        if resource_id:
            return jsonify({
                'success': True,
                'message': 'Resource created',
                'data': {'resource_id': resource_id}
            }), 201
        return jsonify({'success': False, 'message': 'Failed to create resource'}), 500
    except Exception as e:
        logger.error(f"Error creating resource: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@crud_blp.route('/api/resources/<int:resource_id>', methods=['PUT'])
def update_resource(resource_id):
    api, err = _get_api_or_error()
    if err:
        return err

    data = request.get_json()

    try:
        result = api.resources_api.update_resource(resource_id, data)
        if result:
            return jsonify({'success': True, 'message': 'Resource updated'})
        return jsonify({'success': False, 'message': 'Failed to update'}), 500
    except Exception as e:
        logger.error(f"Error updating resource: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@crud_blp.route('/api/resources/<int:resource_id>', methods=['DELETE'])
def delete_resource(resource_id):
    api, err = _get_api_or_error()
    if err:
        return err

    try:
        success = api.resources_api.delete_resource(resource_id)
        if success:
            return jsonify({'success': True, 'message': 'Resource deleted'})
        return jsonify({'success': False, 'message': 'Failed to delete'}), 500
    except Exception as e:
        logger.error(f"Error deleting resource: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@crud_blp.route('/api/resource-types', methods=['GET'])
def list_resource_types():
    api, err = _get_api_or_error()
    if err:
        return err

    try:
        types = api.resources_api.list_resource_types()
        result = []
        for t in types:
            attrs = t.get('attributes', {})
            result.append({
                'sys_id': t.get('id'),
                'name': attrs.get('name', ''),
                'id': attrs.get('id', '')
            })
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        logger.error(f"Error listing resource types: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
