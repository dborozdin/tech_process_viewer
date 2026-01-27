import requests
import json 

class BusinessProcessAPI:
    def __init__(self, db_api):
        self.db_api= db_api
        
    def find_bp_type(self, bp_type_name):
        query="""SELECT NO_CASE
            Ext_
            FROM
            Ext_{apl_business_process_type(.name = \"""" + bp_type_name + """\")
            }
            END_SELECT"""
        requests.packages.urllib3.util.connection.HAS_IPV6 = False
        data_json = requests.post(url=self.db_api.URL_QUERY, headers = {"X-APL-SessionKey": self.db_api.connect_data['session_key']}, data=query).json()
        if data_json.get('count_all') is not None and data_json['count_all']>0:
            bp_type_id= data_json['instances'][0]['id']
            print(f'Found bp type for import with id={bp_type_id}')
            return bp_type_id
        return None
        
    def create_bp_type(self, bp_type_name):
        print(f'create_bp_type(bp_type_name={bp_type_name})')
        query= """{
                    "format":"apl_json_1",
                    "dictionary":"apl_pss_a",
                    "instances":[
                        {"id":0,
                        "index":0,
                        "type":"apl_business_process_type",
                        "attributes":{
                            "name":\""""+bp_type_name+"""\"
                            }
                        }]
                   }"""
        request_result = requests.post(url=self.db_api.URL_QUERY_SAVE, headers = {"X-APL-SessionKey": self.db_api.connect_data['session_key']}, data=query)
        if request_result.status_code==200:
            data_json= request_result.json()
            bp_type_id= data_json['instances'][0]['id']
            print(f'Created bp type for import with id={bp_type_id}')
            return bp_type_id
        else:
            print(f'Bp type crestion error= {request_result}')
            print(f'Error description: {request_result.json()}')
            print(f'Query: {query}')
            return None
        
    def find_or_create_bp_type(self, bp_type_name):
        print(f'find_or_create_bp_type(bp_type_name={bp_type_name})')
        bp_type_sys_id=self.find_bp_type(bp_type_name)
        if bp_type_sys_id is not None:
            return bp_type_sys_id
        else:
            return self.create_bp_type(bp_type_name=bp_type_name)
    
    def find_bp_data_by_id(self, bp_id):
        if bp_id==None or not bp_id.strip():
            print('Error! Bp id not specified!')
            return None
            
        query="""SELECT NO_CASE
            Ext_
            FROM
            Ext_{apl_business_process(.id = \"""" + bp_id + """\")
            }
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

    def find_bp_data_by_sys_id(self, bp_sys_id):
        if bp_sys_id==None:
            print('Error! Bp sys_id not specified!')
            return None
            
        query="""SELECT NO_CASE
            Ext_
            FROM
            Ext_{apl_business_process(.#=#""" + str(bp_sys_id) + """)
            }
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

    def create_business_process(self, bp_id, bp_name, bp_type):
        headers = {"User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36"}
        idx= 0
        query= """{
                    "format":"apl_json_1",
                    "dictionary":"apl_pss_a",
                    "instances":["""
        instances_str="""
                        {   
                            "id":0,
                            "index":"""+str(idx)+""",
                            "type": "apl_business_process",
                            "attributes":
                            {
                                "id": \""""+ bp_id+"""\",
                                "name": \""""+ bp_name+"""\",
                                "customized":false,
                                "type": 
                                {
                                    "id":"""+str(bp_type)+""",
                                    "type": "apl_business_process_type"
                                },
                                "active_version": 
                                {
                                    "id": 0,
                                    "index":"""+str(idx+1)+""",
                                    "type": "apl_business_process_version",
                                    "attributes":{
                                        "id":\""""+ bp_id+"""\",
                                        "name": \""""+ bp_name+"""\",
                                        "customized": false,
                                        "type": 
                                        {
                                            "id":"""+str(bp_type)+""",
                                            "type": "apl_business_process_type"
                                        }
                                    }
                                }
                            }
                        }"""
        query+= instances_str+"""
            ]
        }"""
        #print(query)
        #start_time = time.time()
        requests.packages.urllib3.util.connection.HAS_IPV6 = False
        request_result = requests.post(url=self.db_api.URL_QUERY_SAVE, headers = {"X-APL-SessionKey": self.db_api.connect_data['session_key'], \
                                        "User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36"},\
                                        data=query, timeout=5, verify=False)
        data_json_saved=request_result.json()
        #print(data_json_saved)
        #print("--- %s seconds ---" % (time.time() - start_time))
        if data_json_saved.get('instances')!=None:
            instances= data_json_saved.get('instances')
            created_bp=None
            created_version=None
            for instance in instances:
                if instance.get('type')=='apl_business_process':
                    created_bp=instance.get('id')
                elif instance.get('type')=='apl_business_process_version':
                    created_version=instance.get('id')
            print(f'Created bp with id={created_bp} and version={created_version}')          
            return created_bp, created_version, "created"
        else: 
            print(f'Business process creation error')
            print(f'Error description: {data_json_saved}')
            print(f'Query: {query}')
            return None

    def find_or_create_business_process(self, bp_id, bp_name, bp_type):
        data_json= self.find_bp_data_by_id(bp_id=bp_id)
        if data_json!=None and data_json.get('count_all')!=None:
            if data_json['count_all']==0: #Object not found, let's create it
                #print("Object not found, lets create it!")
                return self.create_business_process(bp_id=bp_id, bp_name=bp_name, bp_type=bp_type)
    
            else:
                found_bp=None
                found_version=None
                for instance in data_json['instances']:
                    if instance.get('type')=='apl_business_process':
                        found_bp=instance.get('id')
                        found_version=instance.get('attributes').get('active_version').get('id')
    
                print(f'Found bp with id={found_bp} and version={found_version}')    
                return found_bp, found_version, "found"
        else:
            print(f'db request error={data_json}')
            return None
        return None

    def get_business_process_resources(self, bp_sys_id):
        print(f'get_business_process_resources with bp_sys_id={bp_sys_id}')
        data_json= self.find_bp_data_by_sys_id(bp_sys_id=bp_sys_id)
        resources=[]
        if data_json!=None and data_json.get('count_all')!=None:
            for instance in data_json['instances']:
                if instance.get('type')=='apl_business_process':
                    resources=instance.get('attributes').get('resources')
        print(f'BP resources={resources}')
        return resources    

    def find_business_process_reference(self, bp, pdf):
        query="""SELECT NO_CASE
            Ext_
            FROM
            Ext_{apl_business_process_reference(.assigned_process=#""" + str(bp) + """ and .item=#"""+ str(pdf)+""")
            }
            END_SELECT"""
        requests.packages.urllib3.util.connection.HAS_IPV6 = False
        data_json = requests.post(url=self.db_api.URL_QUERY, headers = {"X-APL-SessionKey": self.db_api.connect_data['session_key']}, data=query).json()
        return data_json

    def create_business_process_reference(self, bp, pdf):
        headers = {"User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36"}
        idx= 0
        query= """{
                    "format":"apl_json_1",
                    "dictionary":"apl_pss_a",
                    "instances":["""
        instances_str="""
                        {   
                            "id":0,
                            "index":"""+str(idx)+""",
                            "type": "apl_business_process_reference",
                            "attributes":
                            {
                                "assigned_process": 
                                {
                                    "id":"""+str(bp)+""",
                                    "type": "apl_business_process"
                                },
                                "item": 
                                {
                                    "id":"""+str(pdf)+""",
                                    "type": "apl_product_definition_formation"
                                }
                            }
                        }"""
        query+= instances_str+"""
            ]
        }"""
        #print(query)
        #start_time = time.time()
        requests.packages.urllib3.util.connection.HAS_IPV6 = False
        request_result = requests.post(url=self.db_api.URL_QUERY_SAVE, headers = {"X-APL-SessionKey": self.db_api.connect_data['session_key'], \
                                        "User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36"},\
                                        data=query, timeout=5, verify=False)
        data_json_saved=request_result.json()
        #print(data_json_saved)
        #print("--- %s seconds ---" % (time.time() - start_time))
        if data_json_saved.get('instances')!=None:
            instances= data_json_saved.get('instances')
            inst_ids=[]
            for instance in instances:
                if instance.get('type')=='apl_business_process_reference':
                    return instance.get('id')
        else: 
            print(f'Business process reference creation error')
            print(f'Error description: {data_json_saved}')
            print(f'Query: {query}')
            return None

    def find_or_create_bp_reference(self, bp, pdf):
        data_json= self.find_business_process_reference(bp=bp, pdf=pdf)
    
        if data_json.get('count_all')!=None:
            if data_json['count_all']==0: #Object not found, let's create it
                print("Object not found, lets create it!")
                return self.create_business_process_reference(bp=bp, pdf=pdf)
    
            else:
                inst_ids=[]
                bp_ref_id= data_json['instances'][0]['id']
                print(f'Found bp ref with id={bp_ref_id}')
                return bp_ref_id
        else:
            print(f'db request error={data_json}')
            return None

    def set_business_process_elements(self, bp, bp_ver, elements):
        print(f'set_business_process_elements(bp={bp}, bp_ver={bp_ver}, elements= {elements}')
        headers = {"User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36"}
        idx= 0
        query= """{
                    "format":"apl_json_1",
                    "dictionary":"apl_pss_a",
                    "instances":["""
        instances_str="""
                        {   
                            "id": """+str(bp)+""",
                            "type": "apl_business_process",
                            "attributes":
                            {
                                "elements":["""
        for elem in elements:
                                    instances_str+="""
                                    {
                                        "id":"""+str(elem)+""",
                                        "type": "apl_business_process"
                                    },"""
        instances_str+=         """],
                                "active_version": 
                                {
                                   "id":"""+str(bp_ver)+""",
                                   "type": "apl_business_process_version",
                                   "attributes":
                                    {
                                       "elements":["""
        for elem in elements:
                                           instances_str+="""
                                           {
                                                "id":"""+str(elem)+""",
                                                "type": "apl_business_process"
                                           },"""
        instances_str+=              """]
                                     }
                                }
                            }
                        }"""
        query+= instances_str+"""
            ]
        }"""
        requests.packages.urllib3.util.connection.HAS_IPV6 = False
        #print(f'query={query}')
        request_result = requests.post(url=self.db_api.URL_QUERY_SAVE, headers = {"X-APL-SessionKey": self.db_api.connect_data['session_key'], \
                                        "User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36"},\
                                        data=query, timeout=5, verify=False)
        #print(f'request_result={request_result}')
        if request_result.status_code == 200:
            return len(elements)
        else: 
            print(f'Business process elements save error')
            print(f'Error description: {request_result.json()}')
            print(f'Query: {query}')
            return None
            
    def set_business_process_resources(self, bp, bp_ver, resources):
        print(f'set_business_process_resources(bp={bp}, bp_ver={bp_ver}, resources= {resources}')
        headers = {"User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36"}
        idx= 0
        query= """{
                    "format":"apl_json_1",
                    "dictionary":"apl_pss_a",
                    "instances":["""
        instances_str="""
                        {   
                            "id": """+str(bp)+""",
                            "type": "apl_business_process",
                            "attributes":
                            {
                                "resources":["""
        for res in resources:
                                    instances_str+="""
                                    {
                                        "id":"""+str(res)+""",
                                        "type": "apl_business_process_resource"
                                    },"""
        instances_str+=         """],
                                "active_version": 
                                {
                                   "id":"""+str(bp_ver)+""",
                                   "type": "apl_business_process_version",
                                   "attributes":
                                    {
                                       "resources":["""
        for res in resources:
                                           instances_str+="""
                                           {
                                                "id":"""+str(res)+""",
                                                "type": "apl_business_process_resource"
                                           },"""
        instances_str+=              """]
                                     }
                                }
                            }
                        }"""
        query+= instances_str+"""
            ]
        }"""
        requests.packages.urllib3.util.connection.HAS_IPV6 = False
        #print(f'query={query}')
        request_result = requests.post(url=self.db_api.URL_QUERY_SAVE, headers = {"X-APL-SessionKey": self.db_api.connect_data['session_key'], \
                                        "User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36"},\
                                        data=query, timeout=5, verify=False)
        #print(f'request_result={request_result}')
        if request_result.status_code == 200:
            return len(resources)
        else:
            print(f'Business process elements save error')
            print(f'Error description: {request_result.json()}')
            print(f'Query: {query}')
            return None

    def update_business_process(self, bp_sys_id, updates):
        """Update an existing business process

        Args:
            bp_sys_id: Business process system ID
            updates: Dict of attributes to update (name, description, customized, etc.)

        Returns:
            Updated business process instance or None on error
        """
        return self.db_api.update_instance(bp_sys_id, 'apl_business_process', updates)

    def delete_business_process(self, bp_sys_id, soft_delete=True):
        """Delete a business process

        Args:
            bp_sys_id: Business process system ID
            soft_delete: If True, marks as inactive; if False, attempts hard delete

        Returns:
            True on success, False on failure
        """
        return self.db_api.delete_instance(bp_sys_id, 'apl_business_process', soft_delete)

    def get_business_process(self, bp_sys_id):
        """Get a single business process by system ID

        Args:
            bp_sys_id: Business process system ID

        Returns:
            Business process instance or None if not found
        """
        return self.db_api.get_instance(bp_sys_id, 'apl_business_process')

    def list_business_processes(self, filters=None, limit=100):
        """List business processes with optional filtering

        Args:
            filters: Dict of filters or APL query conditions
            limit: Maximum number of results

        Returns:
            List of business process instances
        """
        return self.db_api.query_instances('apl_business_process', filters, limit)

    def add_element_to_process(self, parent_bp_sys_id, child_bp_sys_id):
        """Add a sub-process/element to a business process

        Args:
            parent_bp_sys_id: Parent business process system ID
            child_bp_sys_id: Child business process system ID to add as element

        Returns:
            Updated parent process or None on error
        """
        # Get current elements
        parent = self.get_business_process(parent_bp_sys_id)
        if not parent:
            print(f'Parent business process {parent_bp_sys_id} not found')
            return None

        elements = parent.get('attributes', {}).get('elements', [])

        # Add new element
        elements.append({
            "id": child_bp_sys_id,
            "type": "apl_business_process"
        })

        # Update using existing set_business_process_elements method
        active_version = parent.get('attributes', {}).get('active_version', {})
        active_version_id = active_version.get('id') if isinstance(active_version, dict) else None

        if active_version_id:
            element_ids = [elem['id'] if isinstance(elem, dict) else elem for elem in elements]
            result = self.set_business_process_elements(parent_bp_sys_id, active_version_id, element_ids)
            if result is not None:
                return self.get_business_process(parent_bp_sys_id)

        return None

    def remove_element_from_process(self, parent_bp_sys_id, child_bp_sys_id):
        """Remove a sub-process/element from a business process

        Args:
            parent_bp_sys_id: Parent business process system ID
            child_bp_sys_id: Child business process system ID to remove

        Returns:
            Updated parent process or None on error
        """
        # Get current elements
        parent = self.get_business_process(parent_bp_sys_id)
        if not parent:
            print(f'Parent business process {parent_bp_sys_id} not found')
            return None

        elements = parent.get('attributes', {}).get('elements', [])

        # Remove element
        element_ids = [
            elem['id'] if isinstance(elem, dict) else elem
            for elem in elements
            if (elem['id'] if isinstance(elem, dict) else elem) != child_bp_sys_id
        ]

        # Update using existing set_business_process_elements method
        active_version = parent.get('attributes', {}).get('active_version', {})
        active_version_id = active_version.get('id') if isinstance(active_version, dict) else None

        if active_version_id:
            result = self.set_business_process_elements(parent_bp_sys_id, active_version_id, element_ids)
            if result is not None:
                return self.get_business_process(parent_bp_sys_id)

        return None
