import requests

class FoldersAPI:
    def __init__(self, db_api):
        self.db_api= db_api
        
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
