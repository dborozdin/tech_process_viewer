import requests
from api.pss_api import DatabaseAPI

def query_apl(api, query: str, description: str=None) -> dict:
    """Выполняет запрос к APL и возвращает JSON."""
    print(f'----------------------- query_apl ({description}) ------------------------')
    print(f'Executing DB query: {query}')
    HEADERS = {
        "X-APL-SessionKey": api.connect_data['session_key'],
        "Content-Type": "application/json",
        "Cookie": f"X-Apl-SessionKey={api.connect_data['session_key']}"
    }
    BASE_URL = api.URL_QUERY
    response = requests.post(BASE_URL, headers=HEADERS, data=query.encode("utf-8"))
    response.raise_for_status()
    result = response.json()
    print(f'DB query result: {result}')
    return result

def test_aircrafts():
    print(f'----------------------- test_aircrafts ------------------------')
    # Connect to DB
    server_port = 'http://localhost:7239'
    db = 'pss_moma_08_07_2025'
    user = 'Administrator'
    password = ''

    credentials = f'user={user}&db={db}'
    URL_DB_API = server_port + '/rest'
    api = DatabaseAPI(URL_DB_API, credentials)

    session_key = api.reconnect_db()
    if session_key is None:
        print('Failed to connect to DB')
        return

    print(f'Connected to DB with session_key: {session_key}')

    # Find the "Aircrafts" folder
    folder_data = api.folders_api.find_folder("Aircrafts")
    if not folder_data:
        print("Aircrafts folder not found")
        return

    folder_id, status, content_ids = folder_data
    print(f'Found folder id={folder_id}, content_ids={content_ids}')

    if not content_ids:
        print("No content in Aircrafts folder")
        return

    # content_ids are apl_product_definition_formation ids
    # Query to get the of_product ids
    ids_str = ", ".join(f"#{cid}" for cid in content_ids)
    query_pdf = f"""SELECT NO_CASE
    Ext_
    FROM
    Ext_{{{ids_str}}}
    END_SELECT"""
    pdf_data = query_apl(api, query_pdf, description="Get apl_product_definition_formation instances from Aircrafts folder")
    print(f'PDF query data: {pdf_data}')

    product_ids = []
    for inst in pdf_data.get("instances", []):
        attrs = inst.get("attributes", {})
        of_product = attrs.get("of_product", {})
        if isinstance(of_product, dict) and 'id' in of_product:
            product_ids.append(of_product['id'])

    print(f'Product IDs: {product_ids}')

    if not product_ids:
        print("No product IDs found")
        return

    # Query for the products
    prod_ids_str = ", ".join(f"#{pid}" for pid in product_ids)
    query_products = f"""SELECT NO_CASE
    Ext_
    FROM
    Ext_{{{prod_ids_str}}}
    END_SELECT"""
    products_data = query_apl(api, query_products, description="Get products by IDs from apl_product_definition_formation")
    print(f'Products query data: {products_data}')

    # Output id and name for each product
    for inst in products_data.get("instances", []):
        attrs = inst.get("attributes", {})
        prod_id = attrs.get("id")
        prod_name = attrs.get("name")
        print(f'Product ID: {prod_id}, Name: {prod_name}')

if __name__ == '__main__':
    test_aircrafts()
