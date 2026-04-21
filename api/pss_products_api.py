import requests
from tech_process_viewer.globals import logger

class ProductsAPI:
    def __init__(self, db_api):
        self.db_api= db_api
        
    def create_product(self, prd_id, prd_name, prd_type, prd_source):
        """Create a new product in the database."""
        payload = {
            "format": "apl_json_1",
            "dictionary": "apl_pss_a",
            "instances": [{
                "id": 0,
                "index": 0,
                "type": "apl_product_definition_formation",
                "attributes": {
                    "formation_type": prd_type,
                    "make_or_buy": prd_source,
                    "of_product": {
                        "id": 0,
                        "index": 1,
                        "type": "product",
                        "attributes": {
                            "id": prd_id,
                            "name": prd_name
                        }
                    }
                }
            }]
        }
        headers = self.db_api.get_headers()
        logger.info(f'create_product: POST {self.db_api.URL_QUERY_SAVE}')
        logger.info(f'create_product payload: {payload}')
        request_result = requests.post(
            url=self.db_api.URL_QUERY_SAVE,
            headers=headers,
            json=payload,
            timeout=120
        )
        logger.info(f'create_product response: HTTP {request_result.status_code}, time={request_result.elapsed.total_seconds():.1f}s')
        logger.info(f'create_product response body: {request_result.text[:500]}')
        data_json_saved = request_result.json()
        if data_json_saved.get('instances'):
            instances = data_json_saved.get('instances')
            for instance in instances:
                if instance.get('type') == 'apl_product_definition_formation':
                    inst_sys_id = instance.get('id')
                    logger.info(f'Created product with id {inst_sys_id}')
                    return inst_sys_id
            return None
        else:
            logger.error(f'Product creation error: {data_json_saved}')
            return None
    
    def find_product_version_data_by_product_id(self, prd_id):
        """Find product version by product ID."""
        query = f"""SELECT NO_CASE
            Ext_
            FROM
            Ext_{{apl_product_definition_formation(.of_product->product.id = "{prd_id}")}}
            END_SELECT"""
        requests.packages.urllib3.util.connection.HAS_IPV6 = False
        request_result = requests.post(
            url=self.db_api.URL_QUERY,
            headers={"X-APL-SessionKey": self.db_api.connect_data['session_key']},
            data=query
        )
        if request_result.status_code==200:
            data_json= request_result.json()
        else:
            logger.error(f'find_product_version_by_product_id error: {request_result}')
            logger.error(f'error details: { request_result.json()}')
            logger.error(f'request query: { query}')
            return None
        return data_json

    def find_product_version_by_code(self, code):
        """Find product version by product ID."""
        query = f"""SELECT NO_CASE
            Ext_
            FROM
            Ext_{{apl_product_definition_formation(.code1 = "{code}")}}
            END_SELECT"""
        requests.packages.urllib3.util.connection.HAS_IPV6 = False
        headers= {"X-APL-SessionKey": self.db_api.connect_data['session_key']}
        url=self.db_api.URL_QUERY
        request_result = requests.post(
            url=url,
            headers=headers,
            data=query
        )
        #print(f'headers= {headers}')
        #print(f'url= {url}')
        #print(f'data= {query}')
        
        if request_result.status_code==200:
            data_json= request_result.json()
            if data_json.get('count_all') is not None and data_json.get('count_all')>0:
                pdf_id = data_json['instances'][0]['id']
                logger.info(f'Found product version with id={pdf_id}')
                return pdf_id
        else:
            logger.error(f'find_product_version_by_code error: {request_result}')
            logger.error(f'error details: { request_result.json()}')
            logger.error(f'request query: { query}')
            return None

    def find_product_version_by_product_id(self, prd_id):
        data_json = self.find_product_version_data_by_product_id(prd_id= prd_id)
        if data_json is not None and data_json.get('count_all')>0:
            pdf_sys_id = data_json['instances'][0]['id']
            logger.info(f'Found product version with id={pdf_sys_id}')
            return pdf_sys_id
        return None
    def find_or_create_product(self, prd_id, prd_name, prd_type, prd_source):
        """Find a product by ID or create it if it doesn't exist."""
        data_json = self.find_product_version_data_by_product_id(prd_id= prd_id)
        if data_json.get('count_all') is not None:
            if data_json['count_all'] == 0:  # Object not found, let's create it
                #print("Root product not found, lets create it!")
                return self.create_product(prd_id=prd_id, prd_name=prd_name, prd_type=prd_type, prd_source=prd_source)
            else:
                pdf_id = data_json['instances'][0]['id']
                return pdf_id
        else:
            logger.error(f'db request error={data_json}')
            return None

    def find_product_assembly_by_related(self, pdf_related, pdf_relating):
        query = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{apl_quantified_assembly_component_usage+next_assembly_usage_occurrence(.related_product_definition = #{pdf_related} AND .relating_product_definition=#{pdf_relating})}}
        END_SELECT"""
        requests.packages.urllib3.util.connection.HAS_IPV6 = False
        request_result = requests.post(
            url=self.db_api.URL_QUERY,
            headers={"X-APL-SessionKey": self.db_api.connect_data['session_key']},
            data=query
        )
        if request_result.status_code==200:
            data_json= request_result.json()
        else:
            logger.error(f'find_product_assembly_by_related error: {request_result}')
            logger.error(f'error details: { request_result.json()}')
            logger.error(f'request query: { query}')
            return None
        rel_id= None
        if data_json is not None and data_json['count_all'] > 0:
            rel_id = data_json['instances'][0]['id']
            logger.info(f'Found relation with id={rel_id}')
            return rel_id, "found"
        return None

    def create_product_assembly(self, pdf_related, pdf_relating, quantity, UOM, reference_designator=None):
        """Create a new product assembly in the database."""
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36",
            "X-APL-SessionKey": self.db_api.connect_data['session_key']
        }
        
        # Build attributes
        attributes = {
            "value_component": quantity,
            "related_product_definition": {
                "id": pdf_related,
                "index": 1,
                "type": "apl_product_definition_formation"
            },
            "relating_product_definition": {
                "id": pdf_relating,
                "index": 2,
                "type": "apl_product_definition_formation"
            }
        }
        
        # Add reference_designator if provided
        if reference_designator:
            attributes["reference_designator"] = reference_designator
            
        # Add unit_component only if UOM is valid (not 0)
        if UOM and UOM != 0:
            attributes["unit_component"] = {
                "id": UOM,
                "index": 3,
                "type": "apl_unit"
            }
        
        payload = {
            "format": "apl_json_1",
            "dictionary": "apl_pss_a",
            "instances": [{
                "id": 0,
                "index": 0,
                "type": "apl_quantified_assembly_component_usage+next_assembly_usage_occurrence",
                "attributes": attributes
            }]
        }
        
        requests.packages.urllib3.util.connection.HAS_IPV6 = False
        request_result = requests.post(
            url=self.db_api.URL_QUERY_SAVE,
            headers=headers,
            json=payload,
            timeout=120,
            verify=False
        )
        data_json_saved = request_result.json()
        if data_json_saved.get('instances'):
            instances = data_json_saved.get('instances')
            for instance in instances:
                if instance.get('type') == 'apl_quantified_assembly_component_usage+next_assembly_usage_occurrence':
                    inst_sys_id = instance.get('id')
                    logger.info(f'Created product assembly with id {inst_sys_id}')
                    return inst_sys_id, "created"
            return None
        else:
            logger.error(f'Product assembly creation error')
            logger.error(f'Error description: {data_json_saved}')
            logger.error(f'Query: {payload}')
            return None

    def find_or_create_product_assembly(self, pdf_related, pdf_relating, quantity, UOM):
        """Find a product assembly or create it if it doesn't exist."""
        find_result = self.find_product_assembly_by_related(pdf_related=pdf_related, pdf_relating=pdf_relating)
        if find_result is None:
            return self.create_product_assembly(pdf_related=pdf_related,
                                                pdf_relating=pdf_relating,
                                                quantity=quantity,
                                                UOM=UOM)
        else:
            return find_result

    # New CRUD methods for Products API

    def get_product(self, product_sys_id):
        """Get a single product by system ID"""
        return self.db_api.get_instance(product_sys_id, 'product')

    def list_products(self, filters=None, limit=100):
        """List products with optional filtering"""
        return self.db_api.query_instances('product', filters, limit)

    def update_product(self, product_sys_id, updates):
        """Update an existing product"""
        return self.db_api.update_instance(product_sys_id, 'product', updates)

    def delete_product(self, product_sys_id, soft_delete=True):
        """Delete a product"""
        return self.db_api.delete_instance(product_sys_id, 'product')

    # Product Definition (version) methods

    def get_product_definition(self, pdf_sys_id):
        """Get a single product definition by system ID"""
        return self.db_api.get_instance(pdf_sys_id, 'apl_product_definition_formation')

    def list_product_definitions(self, product_sys_id):
        """List all definitions (versions) for a product"""
        query = f"""SELECT NO_CASE
            Ext_
            FROM
            Ext_{{apl_product_definition_formation(.of_product->product.# = #{product_sys_id})}}
            END_SELECT"""

        result = self.db_api.query_apl(query)
        if result and 'instances' in result:
            return result['instances']
        return []

    def create_product_definition(self, product_sys_id, definition_data):
        """Create a new product definition/version"""
        attributes = {
            "of_product": {
                "id": product_sys_id,
                "type": "product"
            },
            **definition_data
        }

        return self.db_api.create_instance('apl_product_definition_formation', attributes)

    def update_product_definition(self, pdf_sys_id, updates):
        """Update a product definition"""
        return self.db_api.update_instance(pdf_sys_id, 'apl_product_definition_formation', updates)

    def delete_product_definition(self, pdf_sys_id, soft_delete=True):
        """Delete a product definition"""
        return self.db_api.delete_instance(pdf_sys_id, 'apl_product_definition_formation')

    # BOM (Bill of Materials) methods

    def get_bom_structure(self, pdf_sys_id):
        """Get BOM structure (all components) for a product definition"""
        query = f"""SELECT NO_CASE
            Ext_
            FROM
            Ext_{{apl_quantified_assembly_component_usage+next_assembly_usage_occurrence(.relating_product_definition = #{pdf_sys_id})}}
            END_SELECT"""

        result = self.db_api.query_apl(query)
        if result and 'instances' in result:
            return result['instances']
        return []

    def get_bom_item(self, bom_item_sys_id):
        """Get a single BOM item"""
        return self.db_api.get_instance(
            bom_item_sys_id,
            'apl_quantified_assembly_component_usage+next_assembly_usage_occurrence'
        )

    def update_bom_item(self, bom_item_sys_id, updates):
        """Update a BOM item (quantity, unit, reference designator, etc.)"""
        return self.db_api.update_instance(
            bom_item_sys_id,
            'apl_quantified_assembly_component_usage+next_assembly_usage_occurrence',
            updates
        )

    def delete_bom_item(self, bom_item_sys_id, soft_delete=True):
        """Delete a BOM item"""
        return self.db_api.delete_instance(
            bom_item_sys_id,
            'apl_quantified_assembly_component_usage+next_assembly_usage_occurrence'
        )

    def add_component_to_bom(self, parent_pdf_id, component_pdf_id, quantity, unit_id=None, reference_designator=None):
        """Add a component to product's BOM"""
        # Check if already exists
        existing = self.find_product_assembly_by_related(component_pdf_id, parent_pdf_id)
        if existing:
            logger.info(f"Component already exists in BOM: {existing[0]}")
            return existing[0]

        # Create new BOM item
        return self.create_product_assembly(
            pdf_related=component_pdf_id,
            pdf_relating=parent_pdf_id,
            quantity=quantity,
            UOM=unit_id or 1  # Default unit
        )

    # === New methods for PSS-aiR ===

    def search_products(self, text, limit=50):
        """Search products by id or name (case-insensitive LIKE).

        Searches both product (designation/name) and apl_product_definition_formation
        (the PDF objects used by BOM/folder content). APL LIKE on this PSS build
        does not accept '*' wildcards, so we use bare LIKE (substring on PSS side).
        """
        seen = {}
        # Cyrillic LIKE is broken in PSS APL — fall back to filtering in Python.
        is_cyrillic = any('\u0400' <= ch <= '\u04ff' for ch in text or '')
        if is_cyrillic:
            for entity in ('product', 'apl_product_definition_formation'):
                try:
                    q_all = f"""SELECT NO_CASE Ext_ FROM Ext_{{{entity}}} END_SELECT"""
                    res = self.db_api.query_apl(q_all)
                    tl = text.lower()
                    for inst in (res or {}).get('instances', []):
                        attrs = inst.get('attributes', {}) or {}
                        if (tl in (attrs.get('id', '') or '').lower()
                                or tl in (attrs.get('name', '') or '').lower()):
                            seen[inst.get('id')] = inst
                except Exception:
                    pass
        else:
            for entity in ('product', 'apl_product_definition_formation'):
                for field in ('id', 'name'):
                    q_apl = f"""SELECT NO_CASE Ext_ FROM Ext_{{{entity}(.{field} LIKE "{text}")}} END_SELECT"""
                    try:
                        res = self.db_api.query_apl(q_apl)
                        for inst in (res or {}).get('instances', []):
                            seen[inst.get('id')] = inst
                    except Exception:
                        pass
        # Newest matches first — across multiple test runs the same designation
        # may exist many times; the user almost always wants the most recent.
        ordered = sorted(seen.values(), key=lambda i: int(i.get('id') or 0), reverse=True)
        return ordered[:limit]

    def get_product_characteristics(self, pdf_sys_id):
        """Get characteristics for a product definition.

        Combines two sources:
        - apl_property_definition (designed-in properties of the product),
        - apl_characteristic_value attached to this PDF via .item — these include
          values created via the CRUD endpoint /api/crud/characteristics/values.
        """
        out = []
        # 1) Property definitions (existing)
        try:
            q1 = f"""SELECT NO_CASE
            Ext_
            FROM
            Ext_{{apl_property_definition(.definition = #{pdf_sys_id})}}
            END_SELECT"""
            res1 = self.db_api.query_apl(q1)
            if res1 and 'instances' in res1:
                out.extend(res1['instances'])
        except Exception:
            pass

        # 2) Characteristic values attached to this item
        try:
            q2 = f"""SELECT NO_CASE
            Ext_
            FROM
            Ext_{{apl_characteristic_value(.item = #{pdf_sys_id})}}
            END_SELECT"""
            res2 = self.db_api.query_apl(q2)
            for inst in (res2 or {}).get('instances', []) or []:
                attrs = inst.get('attributes', {}) or {}
                # Resolve characteristic name via embedded ref
                char_ref = attrs.get('characteristic') or {}
                char_name = ''
                if isinstance(char_ref, dict) and char_ref.get('id'):
                    try:
                        char_q = f"""SELECT NO_CASE Ext_ FROM Ext_{{#{char_ref['id']}}} END_SELECT"""
                        char_res = self.db_api.query_apl(char_q)
                        for c_inst in (char_res or {}).get('instances', []):
                            c_attrs = c_inst.get('attributes', {}) or {}
                            char_name = c_attrs.get('name') or c_attrs.get('id') or ''
                            break
                    except Exception:
                        pass
                value = attrs.get('scope') or attrs.get('val') or ''
                out.append({
                    'id': inst.get('id'),
                    'type': inst.get('type', 'apl_characteristic_value'),
                    'attributes': {
                        'name': char_name or 'характеристика',
                        'value': value,
                    }
                })
        except Exception:
            pass

        return out

    def get_product_full_info(self, pdf_sys_id):
        """Get full product info: product attrs + PDF attrs + BOM context.

        Returns dict with product designation (id), name, description, code,
        PDF attributes (code1, code2, formation_type, make_or_buy),
        and if this product is part of a BOM — quantity, unit, reference_designator.
        """
        from tech_process_viewer.api.query_helpers import batch_query_by_ids

        # 1. Load PDF instance
        pdf_instances = batch_query_by_ids(self.db_api, [pdf_sys_id], "PDF full info")
        if not pdf_instances:
            return None

        pdf_inst = pdf_instances[0]
        pdf_attrs = pdf_inst.get('attributes', {})

        # 2. Resolve product entity (name, id/designation, description, code)
        of_product = pdf_attrs.get('of_product', {})
        product_data = {}
        if isinstance(of_product, dict) and 'id' in of_product:
            prod_instances = batch_query_by_ids(
                self.db_api, [of_product['id']], "Product for full info"
            )
            if prod_instances:
                product_data = prod_instances[0].get('attributes', {})

        return {
            'sys_id': pdf_sys_id,
            'product_sys_id': of_product.get('id') if isinstance(of_product, dict) else None,
            # Product-level attrs
            'designation': product_data.get('id', ''),
            'name': product_data.get('name', ''),
            'description': product_data.get('description', ''),
            'product_code': product_data.get('code', ''),
            # PDF-level attrs (version)
            'code1': pdf_attrs.get('code1', ''),
            'code2': pdf_attrs.get('code2', ''),
            'formation_type': pdf_attrs.get('formation_type', ''),
            'make_or_buy': pdf_attrs.get('make_or_buy', ''),
            # Raw attrs for extensibility
            'product_attributes': product_data,
            'pdf_attributes': pdf_attrs,
        }

    def get_bom_item_details(self, bom_item_sys_id):
        """Get full BOM item details including resolved unit name.

        Returns dict with quantity, unit_id, unit_name, reference_designator, etc.
        """
        from tech_process_viewer.api.query_helpers import batch_query_by_ids

        inst = self.get_bom_item(bom_item_sys_id)
        if not inst:
            return None

        attrs = inst.get('attributes', {})
        unit_ref = attrs.get('unit_component', {})
        unit_id = unit_ref.get('id') if isinstance(unit_ref, dict) else unit_ref

        # Resolve unit name
        unit_name = ''
        if unit_id:
            unit_instances = batch_query_by_ids(self.db_api, [unit_id], "Unit for BOM item")
            if unit_instances:
                unit_name = unit_instances[0].get('attributes', {}).get('id', '')

        return {
            'bom_sys_id': inst.get('id'),
            'quantity': attrs.get('value_component', ''),
            'unit_sys_id': unit_id,
            'unit_name': unit_name,
            'reference_designator': attrs.get('reference_designator', ''),
            'assembly_item_id': attrs.get('assembly_item_id', ''),
            'description': attrs.get('description', ''),
            'name': attrs.get('name', ''),
        }

    def set_product_characteristic(self, pdf_sys_id, char_name, char_value, char_type=None):
        """Set a characteristic (property) on a product definition.

        Creates or updates apl_property_definition for the given PDF.
        """
        attributes = {
            "name": char_name,
            "value": char_value,
            "definition": {
                "id": pdf_sys_id,
                "type": "apl_product_definition_formation"
            }
        }
        if char_type:
            attributes["property_type"] = char_type

        return self.db_api.create_instance('apl_property_definition', attributes)
