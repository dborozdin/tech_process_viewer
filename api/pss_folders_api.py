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

    # === New methods for PSS-C ===

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
        content_data = folder_attrs.get('content', [])

        if not content_data:
            return {'folder_id': folder_sys_id, 'folder_name': folder_attrs.get('name', ''), 'items': []}

        content_ids = [item.get('id') for item in content_data if item.get('id')]
        if not content_ids:
            return {'folder_id': folder_sys_id, 'folder_name': folder_attrs.get('name', ''), 'items': []}

        from tech_process_viewer.api.query_helpers import batch_query_by_ids
        instances = batch_query_by_ids(self.db_api, content_ids, "Folder content items")

        items = []
        for inst in instances:
            item_type = inst.get('type', '')
            attrs = inst.get('attributes', {})
            if item_type == 'apl_folder':
                category, name = 'folder', attrs.get('name', '')
            elif item_type in ('product', 'apl_product_definition_formation'):
                category, name = 'product', attrs.get('name', '') or attrs.get('id', '')
            elif item_type == 'apl_business_process':
                category, name = 'process', attrs.get('name', '')
            elif item_type in ('apl_document', 'apl_digital_document'):
                category, name = 'document', attrs.get('name', '')
            else:
                category, name = 'other', attrs.get('name', '') or str(inst.get('id', ''))
            items.append({'sys_id': inst.get('id'), 'type': item_type, 'category': category, 'name': name, 'attributes': attrs})

        return {'folder_id': folder_sys_id, 'folder_name': folder_attrs.get('name', ''), 'items': items}
