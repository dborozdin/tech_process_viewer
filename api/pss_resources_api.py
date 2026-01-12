import requests
import json

class ResourcesAPI:
    def __init__(self, db_api):
        self.db_api= db_api
        
    def create_resource(self, res_id, res_name, res_type, bp, item, item_type, value, unit):
        print(f'create_resource with params: res_id={res_id}, res_name={res_name}, res_type={res_type}, bp={bp}, item={item}, item_type={item_type}, value={value}, unit={unit}')
        query_dict = {
            "format": "apl_json_1",
            "dictionary": "apl_pss_a",
            "instances": [
                {
                    "id": 0,
                    "index": 0,
                    "type": "apl_business_process_resource",
                    "attributes": {
                        "id": res_id,
                        "name": res_name,
                        "value_component": value,
                        "type": {
                            "id": res_type,
                            "type": "apl_business_process_resource_type"
                        },
                        "unit_component": {
                            "id": unit,
                            "type": "apl_unit"
                        },
                        "process": {
                            "id": bp,
                            "type": "apl_business_process"
                        },
                        "object": {
                            "id": item,
                            "type": item_type
                        }
                    }
                }
            ]
        }
    
        query = json.dumps(query_dict, ensure_ascii=False)
        requests.packages.urllib3.util.connection.HAS_IPV6 = False
        request_result = requests.post(
            url=self.db_api.URL_QUERY_SAVE,
            headers={"X-APL-SessionKey": self.db_api.connect_data['session_key']},
            data=query
        )
        if request_result.status_code==200:
            data_json= request_result.json()
        else:
            print(f'create resource error: {request_result}')
            print(f'error details: { request_result.json()}')
            print(f'request query: { query}')
            return None
        res_id = data_json['instances'][0]['id']
        print(f'Created resource with id={res_id}')
        return res_id

    def find_resource_by_bp_and_type(self, bp, res_type):
        query = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{apl_business_process_resource(.process = #{bp} AND .type=#{res_type})}}
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
            print(f'Find resource error: {request_result}')
            print(f'error details: { request_result.json()}')
            print(f'request query: { query}')
            return None
        res_id= None
        if data_json['count_all'] > 0:
            res_id = data_json['instances'][0]['id']
            print(f'Found resource with id={res_id}')
        return res_id
    
    def find_or_create_resource(self, res_id, res_name, res_type, bp, bp_ver, item, item_type, value, unit):
        """Find a resource by bp and type or create it if it doesn't exist."""
        res_sys_id= self.find_resource_by_bp_and_type(bp=bp, res_type=res_type) 
        if res_sys_id is None:  
            res_sys_id= self.create_resource(res_id=res_id, res_name=res_name, res_type=res_type, bp=bp, item=item, item_type=item_type, value=value, unit=unit)
            if res_sys_id is not None:
                bp_resources= self.db_api.bp_api.get_business_process_resources(bp_sys_id=bp)
                if bp_resources is not None:
                    bp_resources.append(res_sys_id)
                    bp_resources_new_len= self.db_api.bp_api.set_business_process_resources(bp=bp, bp_ver= bp_ver, resources= bp_resources)
                    if bp_resources_new_len is not None:
                        print(f'Updated resources list for bp {bp}, now bp has {bp_resources_new_len} resources')
            return res_sys_id
        else:
            return res_sys_id 
    
    def create_resource_type(self, res_type_name):
        query_dict = {
            "format": "apl_json_1",
            "dictionary": "apl_pss_a",
            "instances": [
                {
                    "id": 0,
                    "index": 0,
                    "type": "apl_business_process_resource_type",
                    "attributes": {
                        "name": res_type_name,
                    }
                }
            ]
        }
    
        query = json.dumps(query_dict, ensure_ascii=False)
        requests.packages.urllib3.util.connection.HAS_IPV6 = False
        request_result = requests.post(
            url=self.db_api.URL_QUERY_SAVE,
            headers={"X-APL-SessionKey": self.db_api.connect_data['session_key']},
            data=query
        )
        if request_result.status_code==200:
            data_json= request_result.json()
        else:
            print(f'create resource type error: {request_result}')
            print(f'error details: { request_result.json()}')
            print(f'request query: { query}')
            return None
        res_type_id = data_json['instances'][0]['id']
        print(f'Created resource type with id={res_type_id}')
        return res_type_id

    def find_resource_type_by_name(self, res_type_name):
        query = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{apl_business_process_resource_type(.name = "{res_type_name}")}}
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
            print(f'Find resource error: {request_result}')
            print(f'error details: { request_result.json()}')
            print(f'request query: { query}')
            return None
        res_type_id= None
        if data_json['count_all'] > 0:
            res_type_id = data_json['instances'][0]['id']
            print(f'Found resource type with id={res_type_id}')
        return res_type_id
    
    def find_resource_data_by_id(self, res_id):
        if res_id==None:
            print('Error! Resource id not specified!')
            return None

        query="""SELECT NO_CASE
        Ext_
        FROM
        Ext_{apl_business_process_resource(.#=#""" + str(res_id) + """)}
        END_SELECT"""
        requests.packages.urllib3.util.connection.HAS_IPV6 = False
        try:
            response = requests.post(
                url=self.db_api.URL_QUERY,
                headers={"X-APL-SessionKey": self.db_api.connect_data['session_key']},
                data=query
            )

            data_json = response.json()  # может выбросить JSONDecodeError

        except json.JSONDecodeError as e:
            print("❌ Ошибка при разборе JSON:", e)
            print("↩️ Ответ от сервера:", repr(response.text))
            data_json = None  # или {} / [] / raise

        except requests.RequestException as e:
            print("📡 Ошибка при запросе:", e)
            data_json = None

        return data_json

    def find_or_create_resource_type(self, res_type_name):
        """Find a resource type by name or create it if it doesn't exist."""
        res_type_sys_id= self.find_resource_type_by_name(res_type_name=res_type_name)
        if res_type_sys_id is None:
            return self.create_resource_type(res_type_name=res_type_name)
        else:
            return res_type_sys_id
