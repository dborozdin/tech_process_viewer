import requests
from tech_process_viewer.globals import logger


class FoldersAPI:
    def __init__(self, db_api):
        self.db_api = db_api
        
    def find_folder(self, PSS_folder_name):
        print(f'----------------------- find_folder ------------------------')
        print(f'find_folder with PSS_folder_name={PSS_folder_name}')
        query = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{apl_folder(.name = "{PSS_folder_name}")}}
        END_SELECT"""
        print(f'Executing DB query in find_folder: {query}')
        requests.packages.urllib3.util.connection.HAS_IPV6 = False
        request_result = requests.post(
            url=self.db_api.URL_QUERY,
            headers={"X-APL-SessionKey": self.db_api.connect_data['session_key']},
            data=query
        )
        print(f'DB query result in find_folder: {request_result.json() if request_result.status_code==200 else request_result.text}')
        if request_result.status_code==200:
            data_json=request_result.json()
            if data_json and data_json['count_all'] > 0:
                folder_id = data_json['instances'][0]['id']
                print(f'Found folder for import with id={folder_id}')
                content_data = data_json['instances'][0]['attributes']['content']
                print(f'Folder content data={content_data}')
                content = [item['id'] for item in content_data]
                return folder_id, 'found', content
            else:
                return None
        else:
            print(f'Find folder error: {request_result}')
            print(f'Error description: {request_result.json()}')
            print(f'Query: {query}')
            
    def create_folder(self, PSS_folder_name):
        print(f'create_folder with PSS_folder_name={PSS_folder_name}')
        query = f"""{{
            "format":"apl_json_1",
            "dictionary":"apl_pss_a",
            "instances":[
                {{"id":0,
                "index":0,
                "type":"apl_folder",
                "attributes":{{
                    "name":"{PSS_folder_name}"
                    }}
                }}]
        }}"""
        requests.packages.urllib3.util.connection.HAS_IPV6 = False
        request_result = requests.post(
            url=self.db_api.URL_QUERY_SAVE,
            headers={"X-APL-SessionKey": self.db_api.connect_data['session_key']},
            data=query
        )
        if request_result.status_code==200:
            data_json=request_result.json()
            if data_json and data_json['count_all'] > 0:
                folder_id = data_json['instances'][0]['id']
                print(f'Created folder for import with id={folder_id}')
                return folder_id, 'created', []
            else:
                return None
        else:
            print(f'Find folder error: {request_result}')
            print(f'Error description: {request_result.json()}')
            print(f'Query: {query}')
    
    def find_or_create_folder(self, PSS_folder_name):
        """Find a folder by name or create it if it doesn't exist."""
        folder_data= self.find_folder(PSS_folder_name=PSS_folder_name)
        if folder_data is not None:
            return folder_data
        else:
            return self.create_folder(PSS_folder_name=PSS_folder_name)
    
    def add_item_to_folder(self, item, item_type, folder):
        folder_content=[]
    
        elem= { "id": item,
                "type": item_type}
        folder_content.append(elem) 
        folder_content_str= str(folder_content).replace("\'", "\"")
        query= """{
                        "format":"apl_json_1",
                        "dictionary":"apl_pss_a",
                        "instances":[
                                {"id":""" + str(folder) + """,
                                "type":"apl_folder",
                                "attributes":{
                                    "content": """+ folder_content_str+"""
                                }
                            }]
                       }"""
        folder_update_result=requests.post(url=self.db_api.URL_QUERY_SAVE, headers = {"X-APL-SessionKey": self.db_api.connect_data['session_key']}, data=query)
        return folder_update_result.status_code

    def get_folder_content(self, folder_sys_id):
        print(f'get_folder_content with folder_sys_id={folder_sys_id}')
        query = """SELECT NO_CASE
        Ext_
        FROM
        Ext_{apl_folder(.#= #"""+str(folder_sys_id)+""")}
        END_SELECT"""
        requests.packages.urllib3.util.connection.HAS_IPV6 = False
        request_result = requests.post(
            url=self.db_api.URL_QUERY,
            headers={"X-APL-SessionKey": self.db_api.connect_data['session_key']},
            data=query
        )
        content= None
        if request_result.status_code==200:
            data_json=request_result.json()
            if data_json and data_json['count_all'] > 0:
                content_data = data_json['instances'][0]['attributes']['content']
                print(f'Folder content data={content_data}')  
                content = [item['id'] for item in content_data]
                return content
            else:
                return None
        else:
            print(f'Find folder error: {request_result}')
            print(f'Error description: {request_result.json()}')
            print(f'Query: {query}')

    # === New methods for PSS-aiR ===

    def get_all_folders(self):
        """Get all folders in the database."""
        query = """SELECT NO_CASE
        Ext_
        FROM
        Ext_{apl_folder}
        END_SELECT"""
        result = self.db_api.query_apl(query)
        if result and 'instances' in result:
            return result['instances']
        return []

    def rename_folder(self, folder_sys_id, new_name):
        """Rename a folder."""
        return self.db_api.update_instance(folder_sys_id, 'apl_folder', {'name': new_name})

    def delete_folder(self, folder_sys_id):
        """Delete a folder."""
        return self.db_api.delete_instance(folder_sys_id, 'apl_folder')

    def remove_item_from_folder(self, folder_sys_id, item_sys_id):
        """Remove an item from folder content.

        Loads current content, removes the item, and saves back.
        """
        query = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{apl_folder(.# = #{folder_sys_id})}}
        END_SELECT"""
        result = self.db_api.query_apl(query)
        if not result or not result.get('instances'):
            logger.error(f'Folder {folder_sys_id} not found')
            return None

        content_data = result['instances'][0]['attributes'].get('content', [])
        new_content = [item for item in content_data if item.get('id') != item_sys_id]

        if len(new_content) == len(content_data):
            logger.debug(f'Item {item_sys_id} not found in folder {folder_sys_id}')
            return None

        return self.db_api.update_instance(folder_sys_id, 'apl_folder', {'content': new_content})

    def get_folder_with_content_types(self, folder_sys_id):
        """Get folder content with resolved types for each item.

        Combines two sources:
        1. Items listed in folder's `content` attribute (products, documents, processes)
        2. Child folders found via `parent` attribute (subfolder hierarchy)

        Returns dict: {folder_id, folder_name, items: [{sys_id, type, category, name, attributes}]}
        """
        query = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{apl_folder(.# = #{folder_sys_id})}}
        END_SELECT"""
        result = self.db_api.query_apl(query)
        if not result or not result.get('instances'):
            return None

        folder_inst = result['instances'][0]
        folder_attrs = folder_inst.get('attributes', {})
        folder_name = folder_attrs.get('name', '')
        content_data = folder_attrs.get('content', [])

        items = []
        seen_ids = set()

        # 1. Resolve items from content attribute
        content_ids = [item.get('id') for item in content_data if item.get('id')]
        if content_ids:
            from tech_process_viewer.api.query_helpers import batch_query_by_ids
            instances = batch_query_by_ids(self.db_api, content_ids, "Folder content items")

            # Batch-resolve product entities for PDFs (to get name & designation)
            product_ref_ids = []
            pdf_to_product = {}
            for inst in instances:
                if inst.get('type') in ('apl_product_definition_formation',):
                    of_product = inst.get('attributes', {}).get('of_product', {})
                    if isinstance(of_product, dict) and 'id' in of_product:
                        product_ref_ids.append(of_product['id'])
                        pdf_to_product[inst.get('id')] = of_product['id']

            product_map = {}
            if product_ref_ids:
                prod_instances = batch_query_by_ids(
                    self.db_api, product_ref_ids, "Products for folder items"
                )
                for pinst in prod_instances:
                    product_map[pinst.get('id')] = pinst.get('attributes', {})

            for inst in instances:
                item = self._resolve_item(inst, product_map, pdf_to_product)
                items.append(item)
                seen_ids.add(item['sys_id'])

        # 2. Find child folders via parent attribute
        #    Query all folders and filter by parent reference to this folder
        all_folders = self.get_all_folders()
        for inst in all_folders:
            fid = inst.get('id')
            if fid and fid not in seen_ids:
                attrs = inst.get('attributes', {})
                parent_ref = attrs.get('parent')
                parent_id = None
                if isinstance(parent_ref, dict):
                    parent_id = parent_ref.get('id')
                elif isinstance(parent_ref, (int, float)):
                    parent_id = int(parent_ref)
                if parent_id == folder_sys_id:
                    items.append({
                        'sys_id': fid,
                        'type': 'apl_folder',
                        'category': 'folder',
                        'name': attrs.get('name', ''),
                        'attributes': attrs
                    })
                    seen_ids.add(fid)

        return {'folder_id': folder_sys_id, 'folder_name': folder_name, 'items': items}

    def _resolve_item(self, inst, product_map=None, pdf_to_product=None):
        """Resolve a PSS instance to a typed content item."""
        item_type = inst.get('type', '')
        attrs = inst.get('attributes', {})
        result = {'sys_id': inst.get('id'), 'type': item_type, 'attributes': attrs}

        if item_type == 'apl_folder':
            result['category'] = 'folder'
            result['name'] = attrs.get('name', '')
        elif item_type in ('product', 'apl_product_definition_formation'):
            result['category'] = 'product'
            # Resolve product name/designation from product entity
            product_map = product_map or {}
            pdf_to_product = pdf_to_product or {}
            prod_id = pdf_to_product.get(inst.get('id'))
            pattrs = product_map.get(prod_id, {})
            result['name'] = pattrs.get('name', '') or attrs.get('name', '')
            result['designation'] = pattrs.get('id', '') or attrs.get('id', '')
            result['product_code'] = pattrs.get('code', '')
            result['code1'] = attrs.get('code1', '')
            result['formation_type'] = attrs.get('formation_type', '')
            result['make_or_buy'] = attrs.get('make_or_buy', '')
        elif item_type == 'apl_business_process':
            result['category'] = 'process'
            result['name'] = attrs.get('name', '')
        elif item_type in ('apl_document', 'apl_digital_document'):
            result['category'] = 'document'
            result['name'] = attrs.get('name', '')
        else:
            result['category'] = 'other'
            result['name'] = attrs.get('name', '') or str(inst.get('id', ''))

        return result
