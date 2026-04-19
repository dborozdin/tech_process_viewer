import requests
import json

class ResourcesAPI:
    def __init__(self, db_api):
        self.db_api= db_api
        
    def create_resource(self, res_id, res_name, res_type, bp, item, item_type, value, unit):
        print(f'create_resource with params: res_id={res_id}, res_name={res_name}, res_type={res_type}, bp={bp}, item={item}, item_type={item_type}, value={value}, unit={unit}')
        attributes = {
            "id": res_id,
            "name": res_name,
            "value_component": value,
            "type": {
                "id": int(res_type),
                "type": "apl_business_process_resource_type"
            },
            "process": {
                "id": int(bp),
                "type": "apl_business_process"
            },
        }
        # Only include optional refs when they point to a real instance.
        # PSS rejects {id: 0} references, so skip unit/object when not provided.
        try:
            if int(unit) > 0:
                attributes["unit_component"] = {
                    "id": int(unit),
                    "type": "apl_unit"
                }
        except (TypeError, ValueError):
            pass
        try:
            if int(item) > 0:
                attributes["object"] = {
                    "id": int(item),
                    "type": item_type or "organization"
                }
        except (TypeError, ValueError):
            pass
        query_dict = {
            "format": "apl_json_1",
            "dictionary": "apl_pss_a",
            "instances": [
                {
                    "id": 0,
                    "index": 0,
                    "type": "apl_business_process_resource",
                    "attributes": attributes
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

    def find_resources_by_bp_and_type(self, bp, res_type):
        """Найти все ресурсы бизнес-процесса заданного типа (с полными атрибутами).

        Args:
            bp: sys_id бизнес-процесса
            res_type: sys_id типа ресурса (apl_business_process_resource_type)

        Returns:
            list: экземпляры apl_business_process_resource с атрибутами,
                  или пустой список при ошибке/отсутствии
        """
        result = self.db_api.query_apl(
            f"SELECT NO_CASE Ext_ FROM "
            f"Ext_{{apl_business_process_resource(.process = #{bp} AND .type = #{res_type})}}"
            f" END_SELECT"
        )
        if result and 'instances' in result:
            return result['instances']
        return []

    def find_resource_by_bp_and_type(self, bp, res_type):
        """Найти первый ресурс бизнес-процесса заданного типа (только sys_id).

        Делегирует в find_resources_by_bp_and_type.
        """
        instances = self.find_resources_by_bp_and_type(bp, res_type)
        if instances:
            res_id = instances[0].get('id')
            print(f'Found resource with id={res_id}')
            return res_id
        return None
    
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

    # ========== New CRUD Methods for RESTful API ==========

    def get_resource(self, resource_sys_id):
        """Get a single resource by system ID"""
        print(f'get_resource with resource_sys_id={resource_sys_id}')
        return self.db_api.get_instance(resource_sys_id, entity_type='apl_business_process_resource')

    def list_resources(self, filters=None, limit=100):
        """List resources with optional filtering"""
        print(f'list_resources with filters={filters}, limit={limit}')
        return self.db_api.query_instances('apl_business_process_resource', filters=filters, limit=limit)

    def update_resource(self, resource_sys_id, updates):
        """
        Update resource

        Args:
            resource_sys_id: System ID of the resource
            updates: Dictionary with fields to update (value_component, unit_id, object_id)

        Returns:
            Updated resource instance or None on failure
        """
        print(f'update_resource with resource_sys_id={resource_sys_id}, updates={updates}')

        # Map unit_id and object_id to reference structures
        if 'unit_id' in updates:
            unit_id = updates.pop('unit_id')
            if unit_id is not None:
                updates['unit_component'] = {
                    "id": unit_id,
                    "type": "apl_unit"
                }

        if 'object_id' in updates:
            object_id = updates.pop('object_id')
            object_type = updates.pop('object_type', 'apl_product_definition_formation')  # Default type
            if object_id is not None:
                updates['object'] = {
                    "id": object_id,
                    "type": object_type
                }

        return self.db_api.update_instance(resource_sys_id, 'apl_business_process_resource', updates)

    def delete_resource(self, resource_sys_id, soft_delete=True):
        """
        Delete a resource

        Args:
            resource_sys_id: System ID of the resource
            soft_delete: If True, marks as deleted; if False, performs hard delete

        Returns:
            True on success, False on failure
        """
        print(f'delete_resource with resource_sys_id={resource_sys_id}, soft_delete={soft_delete}')
        return self.db_api.delete_instance(resource_sys_id, 'apl_business_process_resource', soft_delete=soft_delete)

    def list_resource_types(self, limit=100):
        """List all resource types"""
        print(f'list_resource_types with limit={limit}')
        return self.db_api.query_instances('apl_business_process_resource_type', filters=None, limit=limit)
