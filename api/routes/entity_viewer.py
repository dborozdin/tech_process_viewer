"""
Generic Entity Viewer routes for browsing and editing any entity type from the database.
"""

from flask import request, jsonify, render_template
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from tech_process_viewer.dict_parser import get_dict_parser
from ..schemas.common_schemas import ErrorSchema


blp = Blueprint(
    'entity_viewer',
    __name__,
    url_prefix='/api/entity-viewer',
    description='Generic entity browser and editor'
)


def get_db_api():
    """Get DatabaseAPI instance from Flask app context"""
    from tech_process_viewer import app as flask_app
    if flask_app.API is None or flask_app.API.connect_data is None:
        abort(401, message="Not connected to database. Please connect first via /api/connect")
    return flask_app.API


@blp.route('/')
class EntityTypesList(MethodView):
    """List all entity types from dictionary"""

    @blp.doc(description="Get list of all entity types defined in the dictionary")
    def get(self):
        """List all entity types"""
        parser = get_dict_parser()

        entity_types = []
        for entity_id, entity in sorted(parser.entities.items()):
            entity_types.append({
                'id': entity.id,
                'name': entity.name,
                'supertype_id': entity.supertype_id,
                'attribute_count': len(entity.attributes),
                'has_subtypes': len(parser.get_subtypes(entity.id)) > 0
            })

        return jsonify({
            'entity_types': entity_types,
            'total': len(entity_types)
        })


@blp.route('/entities/<entity_name>')
class EntityTypeDetail(MethodView):
    """Get details about a specific entity type"""

    @blp.doc(description="Get entity type schema and metadata")
    def get(self, entity_name):
        """Get entity type details"""
        parser = get_dict_parser()
        entity = parser.get_entity_by_name(entity_name)

        if not entity:
            abort(404, message=f"Entity type '{entity_name}' not found")

        # Get all attributes including inherited
        all_attributes = entity.get_all_attributes(parser.entities)

        attributes_info = []
        for attr in all_attributes:
            attr_info = {
                'id': attr.id,
                'name': attr.name,
                'datatype': attr.datatype,
                'python_type': parser.get_python_type(attr.datatype),
                'mandatory': attr.mandatory,
                'is_reference': attr.is_reference(),
                'is_aggregate': attr.is_aggregate()
            }

            if attr.is_reference():
                ref_type_id = attr.get_reference_type()
                if ref_type_id and ref_type_id in parser.entities:
                    attr_info['reference_entity'] = parser.entities[ref_type_id].name

            attributes_info.append(attr_info)

        # Get hierarchy
        hierarchy = parser.get_entity_hierarchy(entity.id)
        hierarchy_names = [parser.entities[eid].name for eid in hierarchy if eid in parser.entities]

        # Get subtypes
        subtypes = parser.get_subtypes(entity.id)
        subtypes_info = [{'id': st.id, 'name': st.name} for st in subtypes]

        return jsonify({
            'entity': {
                'id': entity.id,
                'name': entity.name,
                'supertype_id': entity.supertype_id,
                'hierarchy': hierarchy_names,
                'attributes': attributes_info,
                'subtypes': subtypes_info
            }
        })


@blp.route('/entities/<entity_name>/count')
class EntityInstanceCount(MethodView):
    """Get instance count for a specific entity type"""

    @blp.doc(description="Get count of instances for entity type (fast query)")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def get(self, entity_name):
        """Get instance count"""
        db_api = get_db_api()
        parser = get_dict_parser()

        entity = parser.get_entity_by_name(entity_name)
        if not entity:
            abort(404, message=f"Entity type '{entity_name}' not found")

        # Use optimized /load/ endpoint for faster count
        count = db_api.get_instance_count(entity_name, use_load=True)

        return jsonify({
            'entity_name': entity_name,
            'count': count
        })


@blp.route('/entities/<entity_name>/instances')
class EntityInstancesList(MethodView):
    """List instances of a specific entity type with server-side pagination"""

    @blp.doc(description="Get instances of entity type with pagination (start/size)")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def get(self, entity_name):
        """List instances of entity type"""
        db_api = get_db_api()
        parser = get_dict_parser()

        entity = parser.get_entity_by_name(entity_name)
        if not entity:
            abort(404, message=f"Entity type '{entity_name}' not found")

        # Get pagination parameters (size default = 50 for entity-viewer)
        start = request.args.get('start', 0, type=int)
        size = request.args.get('size', 50, type=int)

        print(f'[entity_viewer] Request: entity={entity_name}, start={start}, size={size}')

        # Server-side pagination using optimized /load/ endpoint
        result = db_api.query_instances_paginated(
            entity_type=entity_name,
            start=start,
            size=size,
            all_attrs=True,
            use_load=True
        )

        print(f'[entity_viewer] Result: count_all={result.get("count_all")}, portion_from={result.get("portion_from")}, instances_count={len(result.get("instances", []))}')

        # Format instances for display
        formatted_instances = []
        for inst in result['instances']:
            formatted = {
                'sys_id': inst.get('id'),
                'type': inst.get('type'),
                'access': inst.get('access'),
                'attributes': inst.get('attributes', {})
            }
            formatted_instances.append(formatted)

        return jsonify({
            'entity_name': entity_name,
            'instances': formatted_instances,
            'count_all': result['count_all'],
            'portion_from': result['portion_from'],
            'size': size
        })

    @blp.doc(description="Create a new instance of entity type")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    def post(self, entity_name):
        """Create a new instance"""
        db_api = get_db_api()
        parser = get_dict_parser()

        entity = parser.get_entity_by_name(entity_name)
        if not entity:
            abort(404, message=f"Entity type '{entity_name}' not found")

        data = request.get_json()
        if not data or 'attributes' not in data:
            abort(400, message="Request must contain 'attributes' field")

        result = db_api.create_instance(entity_name, data['attributes'])
        if result:
            return jsonify({
                'success': True,
                'message': 'Instance created successfully',
                'instance': result
            }), 201
        else:
            abort(500, message="Failed to create instance")


@blp.route('/instances/<int:instance_id>')
class InstanceDetail(MethodView):
    """Get detailed view of a specific instance with resolved references"""

    @blp.doc(description="Get instance details with resolved references")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    @blp.alt_response(404, schema=ErrorSchema, description="Instance not found")
    def get(self, instance_id):
        """Get instance with resolved references"""
        db_api = get_db_api()
        parser = get_dict_parser()

        # Get the instance
        instance = db_api.get_instance(instance_id)
        if not instance:
            abort(404, message=f"Instance {instance_id} not found")

        entity_type = instance.get('type')
        entity = parser.get_entity_by_name(entity_type)

        if not entity:
            # Return raw instance if entity type not in dictionary
            return jsonify({
                'instance': instance,
                'resolved_references': {}
            })

        # Resolve references
        resolved_references = {}
        attributes = instance.get('attributes', {})

        all_attributes = entity.get_all_attributes(parser.entities)

        for attr_def in all_attributes:
            attr_value = attributes.get(attr_def.name)

            if attr_value and attr_def.is_reference():
                # Resolve reference
                if isinstance(attr_value, dict) and 'id' in attr_value:
                    ref_id = attr_value['id']
                    resolved = db_api.get_instance(ref_id)
                    if resolved:
                        resolved_references[attr_def.name] = resolved

                elif isinstance(attr_value, list):
                    # Resolve aggregate references
                    resolved_list = []
                    for item in attr_value:
                        if isinstance(item, dict) and 'id' in item:
                            ref_id = item['id']
                            resolved = db_api.get_instance(ref_id)
                            if resolved:
                                resolved_list.append(resolved)
                    if resolved_list:
                        resolved_references[attr_def.name] = resolved_list

        return jsonify({
            'instance': instance,
            'entity_info': {
                'id': entity.id,
                'name': entity.name,
                'supertype_id': entity.supertype_id
            },
            'resolved_references': resolved_references
        })

    @blp.doc(description="Update instance attributes")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    @blp.alt_response(404, schema=ErrorSchema, description="Instance not found")
    def put(self, instance_id):
        """Update instance attributes"""
        db_api = get_db_api()
        parser = get_dict_parser()

        # Get the instance to determine type
        instance = db_api.get_instance(instance_id)
        if not instance:
            abort(404, message=f"Instance {instance_id} not found")

        entity_type = instance.get('type')
        entity = parser.get_entity_by_name(entity_type)

        # Get update data from request
        update_data = request.get_json()
        if not update_data or 'attributes' not in update_data:
            abort(400, message="Request must contain 'attributes' field")

        attributes_to_update = update_data['attributes']

        # Validate attribute types if entity definition available
        if entity:
            all_attributes = entity.get_all_attributes(parser.entities)
            attr_map = {attr.name: attr for attr in all_attributes}

            validated_updates = {}
            for attr_name, attr_value in attributes_to_update.items():
                if attr_name in attr_map:
                    attr_def = attr_map[attr_name]

                    # Type validation
                    try:
                        validated_value = self._validate_and_convert(
                            attr_value,
                            attr_def,
                            parser
                        )
                        validated_updates[attr_name] = validated_value
                    except ValueError as e:
                        abort(400, message=f"Invalid value for attribute '{attr_name}': {str(e)}")
                else:
                    # Allow unknown attributes (might be valid)
                    validated_updates[attr_name] = attr_value

            attributes_to_update = validated_updates

        # Update instance
        result = db_api.update_instance(instance_id, entity_type, attributes_to_update)

        if result:
            return jsonify({
                'success': True,
                'message': 'Instance updated successfully',
                'instance': result
            })
        else:
            abort(500, message="Failed to update instance")

    def _validate_and_convert(self, value, attr_def, parser):
        """Validate and convert attribute value based on datatype"""
        datatype = attr_def.datatype.lower()

        # Handle references
        if attr_def.is_reference():
            if isinstance(value, dict):
                # Should have 'id' and optionally 'type'
                if 'id' not in value:
                    raise ValueError("Reference must have 'id' field")
                return value
            elif isinstance(value, int):
                # Convert int to reference object
                ref_type_id = attr_def.get_reference_type()
                ref_type_name = parser.entities[ref_type_id].name if ref_type_id in parser.entities else "unknown"
                return {"id": value, "type": ref_type_name}
            elif isinstance(value, list):
                # List of references
                return [self._validate_and_convert(item, attr_def, parser) for item in value]
            else:
                raise ValueError(f"Invalid reference value: {value}")

        # Handle primitive types
        python_type = parser.get_python_type(attr_def.datatype)

        if python_type == 'int':
            return int(value)
        elif python_type == 'float':
            return float(value)
        elif python_type == 'bool':
            if isinstance(value, bool):
                return value
            elif isinstance(value, str):
                return value.lower() in ('true', '1', 'yes')
            else:
                return bool(value)
        elif python_type == 'str':
            return str(value)
        elif python_type == 'list':
            if not isinstance(value, list):
                raise ValueError("Value must be a list")
            return value
        else:
            # Return as-is for unknown types
            return value

    @blp.doc(description="Delete an instance (soft delete)")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    @blp.alt_response(404, schema=ErrorSchema, description="Instance not found")
    def delete(self, instance_id):
        """Delete an instance"""
        db_api = get_db_api()

        instance = db_api.get_instance(instance_id)
        if not instance:
            abort(404, message=f"Instance {instance_id} not found")

        entity_type = instance.get('type')
        success = db_api.delete_instance(instance_id, entity_type, soft_delete=True)

        if success:
            return jsonify({
                'success': True,
                'message': f'Instance {instance_id} deleted successfully'
            })
        else:
            abort(500, message="Failed to delete instance")


@blp.route('/resolve/<int:instance_id>')
class ResolveReference(MethodView):
    """Resolve a single reference for inline display"""

    @blp.doc(description="Get instance details with reference attribute info for inline expansion")
    @blp.alt_response(401, schema=ErrorSchema, description="Not authenticated")
    @blp.alt_response(404, schema=ErrorSchema, description="Instance not found")
    def get(self, instance_id):
        """Resolve a reference for inline display"""
        db_api = get_db_api()
        parser = get_dict_parser()

        instance = db_api.get_instance(instance_id)
        if not instance:
            abort(404, message=f"Instance {instance_id} not found")

        entity_type = instance.get('type')
        entity = parser.get_entity_by_name(entity_type)

        # Identify which attributes are references (for UI to know what can be expanded)
        reference_attrs = []
        if entity:
            all_attributes = entity.get_all_attributes(parser.entities)
            for attr in all_attributes:
                if attr.is_reference():
                    attr_value = instance.get('attributes', {}).get(attr.name)
                    if attr_value:
                        reference_attrs.append({
                            'name': attr.name,
                            'value': attr_value,
                            'is_list': isinstance(attr_value, list)
                        })

        return jsonify({
            'instance': instance,
            'entity_type': entity_type,
            'reference_attributes': reference_attrs
        })
