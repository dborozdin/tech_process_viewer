import requests
from globals import logger

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
