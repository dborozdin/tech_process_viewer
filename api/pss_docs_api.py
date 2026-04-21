import requests
import json

class DocumentsAPI:
    def __init__(self, db_api):
        self.db_api= db_api
        
    def find_doc_type_by_id(self, doc_type_id):
        query="""SELECT NO_CASE
            Ext_
            FROM
            Ext_{document_type(.id = \"""" + doc_type_id + """\")
            }
            END_SELECT"""
        requests.packages.urllib3.util.connection.HAS_IPV6 = False
        data_json = requests.post(url=self.db_api.URL_QUERY, headers = {"X-APL-SessionKey": self.db_api.connect_data['session_key']}, data=query).json()
        if data_json.get('count_all')!=None:
            if data_json['count_all']>0: 
                return data_json['instances'][0]['id']
        return None
    def create_doc_type(self, doc_type_id, doc_type_name):
        print(f'create_doc_type(doc_type_id={doc_type_id}, doc_type_name={doc_type_name})')
        query= """{
                    "format":"apl_json_1",
                    "dictionary":"apl_pss_a",
                    "instances":[
                        {"id":0,
                        "index":0,
                        "type":"document_type",
                        "attributes":{
                            "id":\""""+doc_type_id+"""\",
                            "product_data_type":\""""+doc_type_name+"""\"
                            }
                        }]
                   }"""
        request_result= requests.post(url=self.db_api.URL_QUERY_SAVE, headers = {"X-APL-SessionKey": self.db_api.connect_data['session_key']}, data=query)
        if request_result.status_code == 200:
            data_json= request_result.json()
            doc_type_id= data_json['instances'][0]['id']
            print(f'Created doc type with id={doc_type_id}')
            return doc_type_id
        else:
            print(f'Document type creation error: {request_result}')
            print(f'Error description: {request_result.json()}')
            print(f'Query: {query}')
            return None
        
    def find_or_create_doc_type(self, doc_type_id, doc_type_name):
        print(f'find_or_create_doc_type(doc_type_id={doc_type_id}, doc_type_name={doc_type_name})')
        doc_type_sys_id=self.find_doc_type_by_id(doc_type_id= doc_type_id)
        if doc_type_sys_id is None:
             return self.create_doc_type(doc_type_id=doc_type_id, doc_type_name=doc_type_name)
        else:
            print(f'Found doc type with id={doc_type_id}')
            return doc_type_sys_id

    def find_doc_by_id(self, doc_id):
        print(f'find_doc_by_id with doc_id={doc_id}')
        if doc_id==None or not doc_id.strip():
            print('Error! Doc id not specified!')
            return None
            
        query="""SELECT NO_CASE
            Ext_
            FROM
            Ext_{apl_document(.id = \"""" + doc_id + """\")
            }
            END_SELECT"""
        requests.packages.urllib3.util.connection.HAS_IPV6 = False
        response = requests.post(
                url=self.db_api.URL_QUERY,
                headers={"X-APL-SessionKey": self.db_api.connect_data['session_key']},
                data=query)
        if response.status_code==200:
            try:
                data_json = response.json()  # может выбросить JSONDecodeError
            except json.JSONDecodeError as e:
                print("❌ Ошибка при разборе JSON:", e)
                print("↩️ Ответ от сервера:", repr(response.text))
                data_json = None  # или {} / [] / raise
                return None
            except requests.RequestException as e:
                print("📡 Ошибка при запросе:", e)
                data_json = None
                return None
            instances=data_json.get('instances')
            if instances is not None:
                found_doc=None
                found_version=None
                for instance in instances:
                    if instance.get('type')=='apl_document':
                        found_doc=instance.get('id')
                        found_version=instance.get('attributes').get('active').get('id')
                    #elif instance.get('type')=='apl_digital_document':
                        #found_version=instance.get('id')
                print(f'Found doc with id {found_doc}')    
                return found_doc, found_version, "found"
        else:
            print(f'Document find error: {response}')
            print(f'Error description: {data_json}')
            print(f'Query: {query}')
            return None


    def create_document(self, doc_id, doc_name, doc_type, crc, src_date, stored_doc_id, file_path):
        print(f'create_document with doc_id={doc_id}, doc_name={doc_name}, doc_type={doc_type}, file_path={file_path}')
        if stored_doc_id is None and file_path is not None:
            stored_doc_id= self.upload_blob(file_path=file_path)
        if stored_doc_id is None:
            print('Document stored doc id is not specified!')
            return None
            
        headers = {"User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36"}
        idx= 0
        active_attributes = {
            "of_document": {
                "id": 0,
                "index": idx,
                "type": "apl_document"
            },
            "access_form": {
                "id": stored_doc_id,
                "type": "apl_stored_document"
            }
        }
        
        # Добавление опциональных полей, если они заданы
        if crc is not None:
            active_attributes["crc"] = crc
        if src_date is not None:
            active_attributes["src_date"] = src_date
            active_attributes["end_date_s"] = end_date_s
        
        query_dict = {
            "format": "apl_json_1",
            "dictionary": "apl_pss_a",
            "instances": [
                {
                    "id": 0,
                    "index": idx,
                    "type": "apl_document",
                    "attributes": {
                        "id": doc_id,
                        "name": doc_name,
                        "authentic": False,
                        "incl_in_doc": True,
                        "state": "working",
                        "kind": {
                            "id": doc_type,
                            "type": "document_type"
                        },
                        "active": {
                            "id": 0,
                            "index": idx + 1,
                            "type": "apl_digital_document",
                            "attributes": active_attributes
                        }
                    }
                }
            ]
        }
        
        # При необходимости — сериализация
        query = json.dumps(query_dict, indent=4)
        #print(query)
        #start_time = time.time()
        requests.packages.urllib3.util.connection.HAS_IPV6 = False
        request_result = requests.post(url=self.db_api.URL_QUERY_SAVE, headers = {"X-APL-SessionKey": self.db_api.connect_data['session_key'], \
                                        "User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36"},\
                                        data=query, timeout=5, verify=False)
        if request_result.status_code == 200:
            data_json_saved=request_result.json()
            if data_json_saved.get('instances')!=None:
                instances= data_json_saved.get('instances')
                created_doc=None
                created_version=None
                for instance in instances:
                    if instance.get('type')=='apl_document':
                        created_doc=instance.get('id')
                    elif instance.get('type')=='apl_digital_document':
                        created_version=instance.get('id')
                print(f'Created doc with id {created_doc}')    
                return created_doc, created_version, "created"
        else: 
            print(f'Document creation error: {request_result}')
            print(f'Error description: {data_json_saved}')
            print(f'Query: {query}')
            return None

    def find_or_create_document(self, doc_id, doc_name, doc_type, crc=None, src_date=None, stored_doc_id=None, file_path=None):
        print(f'find_or_create_document with doc_id={doc_id}, doc_name={doc_name}, doc_type={doc_type}, file_path={file_path}')
        doc= self.find_doc_by_id(doc_id=doc_id)
        if doc is None:
            return self.create_document(doc_id=doc_id, doc_name=doc_name, doc_type=doc_type, crc=crc, src_date=src_date, stored_doc_id=stored_doc_id, file_path=file_path)
        else:
            return doc


    def find_document_reference(self, doc, ref_object):
        print(f'find_document_reference with doc={doc}, ref_object={ref_object}')
        query="""SELECT NO_CASE
            Ext_
            FROM
            Ext_{apl_document_reference(.assigned_document=#""" + str(doc) + """ and .item=#"""+ str(ref_object)+""")
            }
            END_SELECT"""
        requests.packages.urllib3.util.connection.HAS_IPV6 = False
        data_json = requests.post(url=self.db_api.URL_QUERY, headers = {"X-APL-SessionKey": self.db_api.connect_data['session_key']}, data=query).json()
        if data_json.get('count_all')!=None:
            if data_json['count_all']>0:
                 doc_ref_id= data_json['instances'][0]['id']
                 print(f'Found doc ref with id={doc_ref_id}')
                 return doc_ref_id, 'found'
        return None

    def create_document_reference(self, doc, ref_object, ref_object_type):
        print(f'create_document_reference with doc={doc}, ref_object={ref_object}, ref_object_type={ref_object_type}')
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
                            "type": "apl_document_reference",
                            "attributes":
                            {
                                "assigned_document": 
                                {
                                    "id":"""+str(doc)+""",
                                    "type": "apl_document"
                                },
                                "item": 
                                {
                                    "id":"""+str(ref_object)+""",
                                     "type": \""""+ ref_object_type+"""\"
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
            for instance in instances:
                if instance.get('type')=='apl_document_reference':
                    doc_ref_id=instance.get('id')
                    print(f'Created doc ref with id={doc_ref_id}')
                    return doc_ref_id, 'created'
        else: 
            print(f'Document reference creation error')
            print(f'Error description: {data_json_saved}')
            print(f'Query: {query}')
            return None

    def find_or_create_document_reference(self, doc, ref_object, ref_object_type):
        print(f'find_or_create_document_reference with doc={doc}, ref_object={ref_object}, ref_object_type={ref_object_type}')
        doc_ref= self.find_document_reference(doc=doc, ref_object=ref_object)
    
        if doc_ref is None:
            return self.create_document_reference(doc=doc, ref_object=ref_object, ref_object_type=ref_object_type)
        else:
            return doc_ref


    def upload_blob(self, file_path):
        # Подготовка данных JSON
        blob_data_to_send = {
            "format": "apl_json_1",
            "dictionary": "apl_pss_a",
            "instances": [
                {
                    "id_tmp": 0,
                    "type": "apl_stored_document",
                    "attributes": {
                        "file_name": file_path.split('/')[-1],
                        "source": "blob1"
                    }
                }
            ]
        }
    
        # Подготовка файла и JSON в multipart-формате
        with open(file_path, 'rb') as file:
            files = {
                'blob1': (file_path.split('/')[-1], file, 'application/octet-stream'),
                'json': (None, json.dumps(blob_data_to_send), 'application/json'),
            }
    
   
            try:
                requests.packages.urllib3.util.connection.HAS_IPV6 = False
                request_result = requests.post(url=self.db_api.URL_UPLOAD, headers = {"X-APL-SessionKey": self.db_api.connect_data['session_key'], \
                                                    "User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36"},\
                                                    files=files, timeout=100, verify=False)
    
                if request_result.status_code == 200:
                    data_json= request_result.json()
                    if data_json.get('instances')!=None:
                        instances= data_json.get('instances')
                        for instance in instances:
                            if instance.get('type')=='apl_stored_document':
                                stored_doc_id= instance.get('id')
                                print(f'Uploaded blob successfully. Stored doc id={stored_doc_id}')
                                return stored_doc_id
                    return None
                else:
                    # При ошибке
                    try:
                        error_json = request_result.json()
                    except ValueError:
                        error_json = None
    
                    error_desc = None
                    if error_json and 'error_description' in error_json and error_json['error_description']:
                        error_desc = error_json['error_description'][0]
                    else:
                        error_desc = request_result.text
                    print(f'Error uploading blob')
                    print(f'Error description: {error_desc}')
                    print(f'Error description: {error_desc}')
                    return None
            
            except requests.RequestException as e:
                # Ошибка запроса (например, таймаут, DNS и т.п.)
                return (None, str(e), None, None)

    # ========== New CRUD Methods for RESTful API ==========

    def get_document(self, doc_sys_id):
        """Get a single document by system ID"""
        print(f'get_document with doc_sys_id={doc_sys_id}')
        return self.db_api.get_instance(doc_sys_id, entity_type='apl_document')

    def list_documents(self, filters=None, limit=100):
        """List documents with optional filtering"""
        print(f'list_documents with filters={filters}, limit={limit}')
        return self.db_api.query_instances('apl_document', filters=filters, limit=limit)

    def update_document(self, doc_sys_id, updates):
        """
        Update document metadata

        Args:
            doc_sys_id: System ID of the document
            updates: Dictionary with fields to update (name, description, kind_id, version_id, status)

        Returns:
            Updated document instance or None on failure
        """
        print(f'update_document with doc_sys_id={doc_sys_id}, updates={updates}')

        # Map kind_id to reference structure if provided
        if 'kind_id' in updates:
            kind_id = updates.pop('kind_id')
            if kind_id is not None:
                updates['kind'] = {
                    "id": kind_id,
                    "type": "document_type"
                }

        return self.db_api.update_instance(doc_sys_id, 'apl_document', updates)

    def delete_document(self, doc_sys_id, soft_delete=True):
        """
        Delete a document

        Args:
            doc_sys_id: System ID of the document
            soft_delete: If True, marks as deleted; if False, performs hard delete

        Returns:
            True on success, False on failure
        """
        print(f'delete_document with doc_sys_id={doc_sys_id}, soft_delete={soft_delete}')
        return self.db_api.delete_instance(doc_sys_id, 'apl_document', soft_delete=soft_delete)

    def get_document_references(self, item_sys_id):
        """
        Get all document references for a specific item

        Args:
            item_sys_id: System ID of the item

        Returns:
            List of document reference instances
        """
        print(f'get_document_references for item_sys_id={item_sys_id}')

        query = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{apl_document_reference(.item=#{item_sys_id})}}
        END_SELECT"""

        return self.db_api.query_apl(query)

    def delete_document_reference(self, doc_ref_sys_id, soft_delete=True):
        """
        Delete a document reference

        Args:
            doc_ref_sys_id: System ID of the document reference
            soft_delete: If True, marks as deleted; if False, performs hard delete

        Returns:
            True on success, False on failure
        """
        print(f'delete_document_reference with doc_ref_sys_id={doc_ref_sys_id}, soft_delete={soft_delete}')
        return self.db_api.delete_instance(doc_ref_sys_id, 'apl_document_reference', soft_delete=soft_delete)
