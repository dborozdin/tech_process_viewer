import inspect
import requests
from .pss_products_api import ProductsAPI
from .pss_folders_api import FoldersAPI
from .pss_bp_api import BusinessProcessAPI
from .pss_orgs_api import OrganizationsAPI
from .pss_resources_api import ResourcesAPI
from .pss_units_api import UnitsAPI
from .pss_docs_api import DocumentsAPI
from globals import logger

class DatabaseAPI:
    def __init__(self, url_db_api, db_credentials):
        self.URL_DB_API = url_db_api
        self.URL_CONNECT = f'{url_db_api}/connect/{db_credentials}'
        self.URL_DISCONNECT = f'{url_db_api}/disconnect'
        self.URL_QUERY_SAVE = f'{url_db_api}/save'
        self.URL_QUERY = f'{url_db_api}&size=100000/query&all_attrs=true'
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
