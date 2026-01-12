import requests
import json

class OrganizationsAPI:
    def __init__(self, db_api):
        self.db_api= db_api
        
    def create_organization(self, org_id, org_name):
        query = f"""{{
            "format":"apl_json_1",
            "dictionary":"apl_pss_a",
            "instances":[
                {{"id":0,
                "index":0,
                "type":"organization",
                "attributes":{{
                    "id":"{org_id}",
                    "name":"{org_name}"
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
            data_json= request_result.json()
        else:
            print(f'create organization error: {request_result}')
            return None
        org_id = data_json['instances'][0]['id']
        print(f'Created organization with id={org_id}')
        return org_id

    def find_organization_by_id(self, org_id):
        query = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{organization(.id = "{org_id}")}}
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
            print(f'Find organization error: {request_result}')
            return None
        org_id= None
        if data_json['count_all'] > 0:
            org_id = data_json['instances'][0]['id']
            print(f'Found organization with id={org_id}')
        return org_id
    
    def find_or_create_organization(self, org_id, org_name):
        """Find a organization by id or create it if it doesn't exist."""
        org_sys_id= self.find_organization_by_id(org_id= org_id) 
        if org_sys_id is None:  
            return self.create_organization(org_id, org_name)
        else:
            return org_sys_id 
    
    def find_organizations_relation(self, org_related, org_relating):
        query = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{organization_relationship(.related_organization = #{str(org_related)} and .relating_organization= #{str(org_relating)})}}
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
            print(f'Find organization relation error: {request_result}')
            return None
        org_rel_id= None
        if data_json['count_all'] > 0:
            org_rel_id = data_json['instances'][0]['id']
            print(f'Found organization relation with id={org_rel_id}')
        else:
            print('No relation found')
        return org_rel_id

    def create_organizations_relation(self, org_related, org_relating):
        query_dict = {
            "format": "apl_json_1",
            "dictionary": "apl_pss_a",
            "instances": [
                {
                    "id": 0,
                    "index": 0,
                    "type": "organization_relationship",
                    "attributes": {
                        "related_organization": {
                            "id": org_related,
                            "type": "organization"
                        },
                        "relating_organization": {
                            "id": org_relating,
                            "type": "organization"
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
            print(f'create organization relation error: {request_result}')
            print(f'error details: { request_result.json()}')
            print(f'request query: { query}')
            return None
        org_rel_id = data_json['instances'][0]['id']
        print(f'Created organization relation with id={org_rel_id}')
        return org_rel_id

    def find_or_create_organizations_relation(self, org_related, org_relating):
        """Find a organization relation by org_related, org_relating or create it if it doesn't exist."""
        org_rel_id= self.find_organizations_relation(org_related=org_related , org_relating=org_relating) 
        if org_rel_id is None:  
            return self.create_organizations_relation(org_related=org_related, org_relating=org_relating)
        else:
            return org_rel_id 