import requests
from tech_process_viewer.globals import logger

class ProductsAPI:
    def __init__(self, db_api):
        self.db_api= db_api
        
    def create_product(self, prd_id, prd_name, prd_type, prd_source):
        """Create a new product in the database."""
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36",
            "X-APL-SessionKey": self.db_api.connect_data['session_key']
        }
        idx = 0
        query = f"""{{
            "format":"apl_json_1",
            "dictionary":"apl_pss_a",
            "instances":[
                {{
                    "id":0,
                    "index":{idx},
                    "type":"apl_product_definition_formation",
                    "attributes":{{
                        "formation_type":"{prd_type}",
                        "make_or_buy":"{prd_source}",
                        "of_product":{{
                            "id":0,
                            "index":{idx + 1},
                            "type":"product",
                            "attributes":{{
                                "id":"{prd_id}",
                                "name":"{prd_name}"
                            }}
                        }}
                    }}
                }}
            ]
        }}"""
        requests.packages.urllib3.util.connection.HAS_IPV6 = False
        request_result = requests.post(
            url=self.db_api.URL_QUERY_SAVE,
            headers=headers,
            data=query,
            timeout=5,
            verify=False
        )
        data_json_saved = request_result.json()
        if data_json_saved.get('instances'):
            instances = data_json_saved.get('instances')
            for instance in instances:
                if instance.get('type') == 'apl_product_definition_formation':
                    inst_sys_id=instance.get('id')
                    logger.info(f'Found product with id {inst_sys_id}')
                    return inst_sys_id
            return None
        else:
            logger.error(f'Product creation error')
            logger.error(f'Error description: {data_json_saved}')
            logger.error(f'Query: {query}')
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

    def create_product_assembly(self, pdf_related, pdf_relating, quantity, UOM):
        """Create a new product assemply in the database."""
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36",
            "X-APL-SessionKey": self.db_api.connect_data['session_key']
        }
        idx = 0
        query = f"""{{
            "format":"apl_json_1",
            "dictionary":"apl_pss_a",
            "instances":[
                {{
                    "id":0,
                    "index":{idx},
                    "type":"apl_quantified_assembly_component_usage+next_assembly_usage_occurrence",
                    "attributes":{{
                        "value_component": {quantity},
                        "related_product_definition":{{
                            "id": {pdf_related},
                            "type":"apl_product_definition_formation"
                        }},
                        "relating_product_definition":{{
                            "id": {pdf_relating},
                            "type":"apl_product_definition_formation"
                        }},
                        "unit_component":{{
                            "id": {UOM},
                            "type":"apl_unit"
                        }}
                    }}
                }}
            ]
        }}"""
        requests.packages.urllib3.util.connection.HAS_IPV6 = False
        request_result = requests.post(
            url=self.db_api.URL_QUERY_SAVE,
            headers=headers,
            data=query,
            timeout=5,
            verify=False
        )
        data_json_saved = request_result.json()
        if data_json_saved.get('instances'):
            instances = data_json_saved.get('instances')
            for instance in instances:
                if instance.get('type') == 'apl_quantified_assembly_component_usage+next_assembly_usage_occurrence':
                    inst_sys_id=instance.get('id')
                    logger.info(f'Created product assembly with id {inst_sys_id}')
                    return inst_sys_id, "created"
            return None
        else:
            logger.error(f'Product assembly creation error')
            logger.error(f'Error description: {data_json_saved}')
            logger.error(f'Query: {query}')
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
        return self.db_api.delete_instance(product_sys_id, 'product', soft_delete)

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
        return self.db_api.delete_instance(pdf_sys_id, 'apl_product_definition_formation', soft_delete)

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
            'apl_quantified_assembly_component_usage+next_assembly_usage_occurrence',
            soft_delete
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
