import inspect
import json
import requests
import time
from .pss_products_api import ProductsAPI
from .pss_folders_api import FoldersAPI
from .pss_bp_api import BusinessProcessAPI
from .pss_orgs_api import OrganizationsAPI
from .pss_resources_api import ResourcesAPI
from .pss_units_api import UnitsAPI
from .pss_docs_api import DocumentsAPI
from tech_process_viewer.globals import logger

class DatabaseAPI:
    def __init__(self, url_db_api, db_credentials):
        self.URL_DB_API = url_db_api
        self.URL_CONNECT = f'{url_db_api}/connect/{db_credentials}'
        self.URL_DISCONNECT = f'{url_db_api}/disconnect'
        self.URL_QUERY_SAVE = f'{url_db_api}/save'
        self.URL_QUERY = f'{url_db_api}&size=50/query&all_attrs=true'
        self.URL_UPLOAD = f'{url_db_api}/upload'
        self.connect_data = None
        self.folders_api= FoldersAPI(self)
        self.products_api= ProductsAPI(self)
        self.bp_api= BusinessProcessAPI(self)
        self.org_api= OrganizationsAPI(self)
        self.resources_api= ResourcesAPI(self)
        self.units_api= UnitsAPI(self)
        self.docs_api=DocumentsAPI(self)

    def disconnect_db(self):
        """disconnect to the database."""
        print(f'self.URL_DISCONNECT={self.URL_DISCONNECT}')
        
        # Disconnect from db
        headers= None
        if self.connect_data is not None:
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36",
                "X-APL-SessionKey": self.connect_data['session_key']
            }
        disconnect_data = requests.get(self.URL_DISCONNECT, headers= headers)
        print(disconnect_data)
     
    def reconnect_db(self):
        """Reconnect to the database."""
        print(f'self.URL_DB_API={self.URL_DB_API}')
        print(f'self.URL_CONNECT={self.URL_CONNECT}')
        print(f'self.URL_DISCONNECT={self.URL_DISCONNECT}')
        print(f'self.URL_QUERY_SAVE={self.URL_QUERY_SAVE}')
        print(f'self.URL_QUERY={self.URL_QUERY}')
        print(f'self.URL_UPLOAD={self.URL_UPLOAD}')

        headers= None
        if self.connect_data is not None:
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36",
                "X-APL-SessionKey": self.connect_data['session_key']
            }
            print(f'Disconnect headers: {headers}')
                  
        # Disconnect from db
        disconnect_data = requests.get(self.URL_DISCONNECT, headers= headers)
        print(disconnect_data)
        # Connect to db
        self.connect_data = {}
        connect_result= requests.get(self.URL_CONNECT)
        print(f'connect_result={connect_result}')
        
        if connect_result.status_code==200:
            connect_data=connect_result.json()
        else:
            logger.error(f'Error connecting db')
            logger.error(f'Error details: {connect_result}')
            return None

        # Get session key

        if 'session_key' in connect_data:
            self.connect_data['session_key']= connect_data.get('session_key')
            logger.info(f"Connected to DB. Session_key: {self.connect_data['session_key']}")
            return self.connect_data['session_key']
        else:
            logger.error('Error connecting DB')
            logger.error(f'{connect_result}')
            return None

    def get_headers(self):
        """Get request headers with session key for authenticated requests"""
        if self.connect_data is None or 'session_key' not in self.connect_data:
            raise ValueError("Not connected to database. Call reconnect_db() first.")

        return {
            "User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36",
            "X-APL-SessionKey": self.connect_data['session_key'],
            "Content-Type": "application/json"
        }

    def query_apl(self, query_string, url=None):
        """Execute APL query and return JSON response

        Args:
            query_string: APL query to execute
            url: Optional custom URL (for pagination). If None, uses self.URL_QUERY
        """
        try:
            headers = self.get_headers()
            target_url = url if url else self.URL_QUERY
            print(f'---------------DB QUERY---------------')

            # 1. Запоминаем время начала
            start_time = time.perf_counter()
            print(f'target_url={target_url}')
            print(f'headers={headers}')
            print(f'query_string={query_string}')

            requests.packages.urllib3.util.connection.HAS_IPV6 = False
            response = requests.post(target_url, headers=headers, data=query_string.encode("utf-8"))
            # 2. Запоминаем время окончания
            end_time = time.perf_counter()
            # 3. Вычисляем разницу
            execution_time = end_time - start_time
            print(f"Время выполнения: {execution_time:.6f} секунд")
            print(f'--------------------------------------')
            response.raise_for_status()
            return json.loads(response.text, strict=False)
        except requests.RequestException as e:
            logger.error(f"Query error: {e}")
            return None

    def load_entity_instances(self, entity_type, start=0, size=50, all_attrs=True):
        """Load instances of entity type using optimized GET /load/ endpoint

        More efficient than POST /query for simple entity type queries.

        Args:
            entity_type: Entity type to load (e.g., 'organization', 'apl_product')
            start: Starting index (0-based)
            size: Number of instances to return
            all_attrs: Whether to return all attributes

        Returns:
            {
                'instances': [...],
                'count_all': int,
                'portion_from': int
            }
        """
        try:
            headers = self.get_headers()
            attrs_param = "true" if all_attrs else "false"

            # Build optimized GET URL
            # Format: /rest&size=<size>&start=<start>/load/t=e&ent=<entity>&all_attrs=<true|false>
            url = f"{self.URL_DB_API}&size={size}&start={start}/load/t=e&ent={entity_type}&all_attrs={attrs_param}"

            print(f'---------------DB LOAD (GET)---------------')
            start_time = time.perf_counter()
            print(f'url={url}')

            requests.packages.urllib3.util.connection.HAS_IPV6 = False
            response = requests.get(url, headers=headers)

            end_time = time.perf_counter()
            execution_time = end_time - start_time
            print(f"Время выполнения: {execution_time:.6f} секунд")
            print(f'-------------------------------------------')

            response.raise_for_status()
            result = json.loads(response.text, strict=False)

            instances = result.get('instances', [])
            count_all = result.get('count_all', len(instances))
            portion_from = result.get('portion_from', start)

            print(f'PSS Response: count_all={count_all}, portion_from={portion_from}, received_instances={len(instances)}')
            if instances:
                print(f'First instance id: {instances[0].get("id")}, Last instance id: {instances[-1].get("id")}')

            # Check if PSS respected the start parameter
            # If portion_from is 0 but we requested start > 0, PSS might not support pagination
            actual_portion_from = portion_from
            if portion_from == 0 and start > 0:
                if len(instances) > start:
                    print(f'PSS ignored start parameter - applying client-side offset: skip first {start} instances')
                    instances = instances[start:]
                    actual_portion_from = start
                else:
                    # PSS didn't return enough instances to satisfy the offset
                    print(f'PSS returned {len(instances)} instances but start={start}, returning empty list')
                    print(f'NOTE: /load/ endpoint may not support pagination. Consider using POST /query instead.')
                    instances = []

            # Ensure we only return the requested size (PSS may return more)
            if len(instances) > size:
                print(f'Limiting instances from {len(instances)} to {size}')
                instances = instances[:size]

            if instances:
                print(f'After pagination fix - First id: {instances[0].get("id")}, Last id: {instances[-1].get("id")}, count: {len(instances)}')

            return {
                'instances': instances,
                'count_all': count_all,
                'portion_from': actual_portion_from
            }

        except requests.RequestException as e:
            logger.error(f"Load error for {entity_type}: {e}")
            return {'instances': [], 'count_all': 0, 'portion_from': start}
        except Exception as e:
            logger.error(f"Unexpected error loading {entity_type}: {e}")
            return {'instances': [], 'count_all': 0, 'portion_from': start}

    def query_instances_paginated(self, entity_type, start=0, size=50, all_attrs=True, filters=None, use_load=False):
        """Query instances with server-side pagination

        Args:
            entity_type: Entity type to query
            start: Starting index (0-based)
            size: Number of instances to return
            all_attrs: Whether to return all attributes (False for faster count)
            filters: Optional filter string or dict
            use_load: If True, use optimized GET /load/ endpoint (faster for simple queries)

        Returns:
            {
                'instances': [...],
                'count_all': int,      # total number of matching instances
                'portion_from': int    # starting index of this portion
            }
        """
        # For simple queries without filters, use optimized /load/ endpoint
        if use_load and not filters:
            return self.load_entity_instances(entity_type, start, size, all_attrs)

        try:
            # Build URL with pagination parameters
            attrs_param = "true" if all_attrs else "false"
            url = f"{self.URL_DB_API}&start={start}&size={size}/query&all_attrs={attrs_param}"

            # Build query
            if isinstance(filters, str) and filters:
                query = f"SELECT NO_CASE Ext_ FROM Ext_{{{entity_type}({filters})}} END_SELECT"
            elif isinstance(filters, dict) and filters:
                conditions = []
                for field, value in filters.items():
                    if isinstance(value, str):
                        conditions.append(f".{field} LIKE '{value}'")
                    else:
                        conditions.append(f".{field} = {value}")
                filter_clause = " AND ".join(conditions)
                query = f"SELECT NO_CASE Ext_ FROM Ext_{{{entity_type}({filter_clause})}} END_SELECT"
            else:
                query = f"SELECT NO_CASE Ext_ FROM Ext_{{{entity_type}}} END_SELECT"

            result = self.query_apl(query, url=url)

            if result:
                return {
                    'instances': result.get('instances', []),
                    'count_all': result.get('count_all', len(result.get('instances', []))),
                    'portion_from': result.get('portion_from', start)
                }
            return {'instances': [], 'count_all': 0, 'portion_from': start}

        except Exception as e:
            logger.error(f"Error querying paginated instances of {entity_type}: {e}")
            return {'instances': [], 'count_all': 0, 'portion_from': start}

    def get_instance_count(self, entity_type, filters=None, use_load=False):
        """Get count of instances for entity type (fast, uses all_attrs=false)

        Args:
            entity_type: Entity type to count
            filters: Optional filter string or dict
            use_load: If True, use optimized GET /load/ endpoint

        Returns:
            int: Number of instances
        """
        # Request with size=1 and all_attrs=false - we only need count_all
        result = self.query_instances_paginated(entity_type, start=0, size=1, all_attrs=False, filters=filters, use_load=use_load)
        return result.get('count_all', 0)

    def get_instance(self, sys_id, entity_type=None):
        """Get a single instance by system ID

        Args:
            sys_id: System ID of the instance
            entity_type: Optional entity type filter

        Returns:
            Instance data dict or None if not found
        """
        try:
            if entity_type:
                query = f"SELECT NO_CASE Ext_ FROM Ext_{{{entity_type}(.# = #{sys_id})}} END_SELECT"
            else:
                query = f"SELECT NO_CASE Ext_ FROM Ext_{{#{sys_id}}} END_SELECT"

            result = self.query_apl(query)

            if result and 'instances' in result and len(result['instances']) > 0:
                return result['instances'][0]
            return None
        except Exception as e:
            logger.error(f"Error getting instance {sys_id}: {e}")
            return None

    def query_instances(self, entity_type, filters=None, limit=100):
        """Generic query method with filtering

        Args:
            entity_type: Entity type to query (e.g., 'apl_business_process')
            filters: Dict of field->value filters or APL query conditions
            limit: Maximum number of results

        Returns:
            List of instances
        """
        try:
            # Build query based on filters
            if isinstance(filters, str):
                # Direct APL query condition
                filter_clause = filters
            elif isinstance(filters, dict) and filters:
                # Build filter clause from dict
                conditions = []
                for field, value in filters.items():
                    if isinstance(value, str):
                        conditions.append(f".{field} LIKE '{value}'")
                    else:
                        conditions.append(f".{field} = {value}")
                filter_clause = " AND ".join(conditions)
            else:
                filter_clause = ""

            if filter_clause:
                query = f"SELECT NO_CASE Ext_ FROM Ext_{{{entity_type}({filter_clause})}} END_SELECT"
            else:
                query = f"SELECT NO_CASE Ext_ FROM Ext_{{{entity_type}}} END_SELECT"

            result = self.query_apl(query)

            if result and 'instances' in result:
                return result['instances'][:limit]
            return []
        except Exception as e:
            logger.error(f"Error querying instances of {entity_type}: {e}")
            return []

    def update_instance(self, sys_id, entity_type, updates):
        """Update an existing instance

        Args:
            sys_id: System ID of instance to update
            entity_type: Entity type (e.g., 'apl_business_process')
            updates: Dict of attribute updates

        Returns:
            Updated instance data or None on error
        """
        try:
            # 1. Fetch existing instance
            existing = self.get_instance(sys_id, entity_type)
            if not existing:
                logger.error(f"Instance {sys_id} not found for update")
                return None

            # 2. Merge updates into attributes
            if 'attributes' not in existing:
                existing['attributes'] = {}
            existing['attributes'].update(updates)

            # 3. Prepare payload for save
            payload = {
                "format": "apl_json_1",
                "dictionary": "apl_pss_a",
                "instances": [existing]
            }

            # 4. POST to save endpoint
            headers = self.get_headers()
            response = requests.post(self.URL_QUERY_SAVE, json=payload, headers=headers)
            response.raise_for_status()

            result = response.json()

            if result and 'instances' in result and len(result['instances']) > 0:
                logger.info(f"Successfully updated instance {sys_id}")
                return result['instances'][0]
            else:
                logger.error(f"Update failed for instance {sys_id}")
                return None

        except requests.RequestException as e:
            logger.error(f"Error updating instance {sys_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error updating instance {sys_id}: {e}")
            return None

    def delete_instance(self, sys_id, entity_type, soft_delete=True):
        """Delete an instance (soft delete by default)

        Args:
            sys_id: System ID of instance to delete
            entity_type: Entity type
            soft_delete: If True, set status to deleted/inactive; if False, attempt hard delete

        Returns:
            True on success, False on failure
        """
        try:
            if soft_delete:
                # Soft delete: update status field
                # Try common status field names
                status_updates = {
                    'active': False,
                    'deleted': True,
                    'status': 'deleted'
                }

                result = self.update_instance(sys_id, entity_type, status_updates)
                return result is not None
            else:
                # Hard delete: attempt to delete via backend API
                # Note: Backend may not support hard delete - check documentation
                logger.warning(f"Hard delete not implemented for {entity_type}. Using soft delete.")
                return self.delete_instance(sys_id, entity_type, soft_delete=True)

        except Exception as e:
            logger.error(f"Error deleting instance {sys_id}: {e}")
            return False

    def create_instance(self, entity_type, attributes, index=0):
        """Create a new instance

        Args:
            entity_type: Entity type (e.g., 'apl_business_process')
            attributes: Dict of attributes for the new instance
            index: Instance index (default 0)

        Returns:
            Created instance data or None on error
        """
        try:
            payload = {
                "format": "apl_json_1",
                "dictionary": "apl_pss_a",
                "instances": [{
                    "id": 0,  # 0 for new instances
                    "index": index,
                    "type": entity_type,
                    "attributes": attributes
                }]
            }

            headers = self.get_headers()
            response = requests.post(self.URL_QUERY_SAVE, json=payload, headers=headers)
            response.raise_for_status()

            result = response.json()

            if result and 'instances' in result and len(result['instances']) > 0:
                logger.info(f"Successfully created instance of type {entity_type}")
                return result['instances'][0]
            else:
                logger.error(f"Creation failed for {entity_type}")
                return None

        except requests.RequestException as e:
            logger.error(f"Error creating instance of {entity_type}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating instance of {entity_type}: {e}")
            return None
