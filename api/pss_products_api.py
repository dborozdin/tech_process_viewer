import requests

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
                    return instance.get('id')
            return None
        else:
            print(f'Product creation error')
            print(f'Error description: {data_json_saved}')
            print(f'Query: {query}')
            return None
    
    def find_product_version_by_product_id(self, prd_id):
        """Find product version by product ID."""
        query = f"""SELECT NO_CASE
            Ext_
            FROM
            Ext_{{apl_product_definition_formation(.of_product->product.id = "{prd_id}")}}
            END_SELECT"""
        requests.packages.urllib3.util.connection.HAS_IPV6 = False
        data_json = requests.post(
            url=self.db_api.URL_QUERY,
            headers={"X-APL-SessionKey": self.db_api.connect_data['session_key']},
            data=query
        ).json()
        return data_json
    
    def find_or_create_product(self, prd_id, prd_name, prd_type, prd_source):
        """Find a product by ID or create it if it doesn't exist."""
        data_json = self.find_product_version_by_product_id(prd_id= prd_id)  
        if data_json.get('count_all') is not None:
            if data_json['count_all'] == 0:  # Object not found, let's create it
                print("Root product not found, lets create it!")
                return self.create_product(prd_id=prd_id, prd_name=prd_name, prd_type=prd_type, prd_source=prd_source)
            else:
                pdf_id = data_json['instances'][0]['id']
                return pdf_id
        else:
            print(f'db request error={data_json}')
            return None