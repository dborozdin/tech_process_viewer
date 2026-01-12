import requests
import json

class UnitsAPI:
    def __init__(self, db_api):
        self.db_api= db_api
        
    def create_conversion_based_unit(self, unit_id, unit_name, base_unit, conversion_factor):
        query_dict = {
            "format": "apl_json_1",
            "dictionary": "apl_pss_a",
            "instances": [
                {
                    "id": 0,
                    "index": 0,
                    "type": "conversion_based_unit",
                    "attributes": {
                        "id": unit_id,
                        "name": unit_name,
                        "conversion_factor": {
                            "id": 0,
                            "index": 1,
                            "type": "measure_with_unit",
                            "attributes": {
                                "value_component": conversion_factor,
                                "unit_component": {
                                    "id": base_unit,
                                    "type": "si_unit"
                                }
                            }
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
            print(f'create unit error: {request_result}')
            print(f'error details: { request_result.json()}')
            print(f'request query: { query}')
            return None
        unit_id = data_json['instances'][0]['id']
        print(f'Created unit with id={unit_id}')
        return res_id

    def find_unit_by_id(self, unit_id):
        query = f"""SELECT NO_CASE
        Ext_
        FROM
        Ext_{{apl_unit(.id = "{unit_id}") }}
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
            print(f'Find unit error: {request_result}')
            print(f'error details: { request_result.json()}')
            print(f'request query: { query}')
            return None
        unit_id= None
        if data_json['count_all'] > 0:
            unit_id = data_json['instances'][0]['id']
            print(f'Found unit with id={unit_id}')
        return unit_id
    
    def find_or_create_conv_based_unit(self, unit_id, unit_name, base_unit, conversion_factor):
        """Find a unit by id or create it if it doesn't exist."""
        unit_id= self.find_unit_by_id(unit_id=unit_id) 
        if unit_id is None:  
            return self.create_conversion_based_unit(unit_id=unit_id, unit_name=unit_name, base_unit=base_unit, conversion_factor=conversion_factor)
        else:
            return unit_id 
  