#!/usr/bin/env python3
"""
Test script to check materials fetching for technical process details.
"""

import requests
import json

# Assuming the app is running on localhost:5000
BASE_URL = 'http://localhost:5000'

def test_materials_fetch(tech_proc_id):
    url = f'{BASE_URL}/api/technical_process_details/{tech_proc_id}'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        print("Technical process data:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        materials = data.get('materials', [])
        print(f"\nMaterials found: {len(materials)}")
        for mat in materials:
            print(f"Name: {mat.get('name')}, Code: {mat.get('code')}, ID: {mat.get('id')}, Standard: {mat.get('standart')}, UOM: {mat.get('uom')}")
    else:
        print(f"Error: {response.status_code} - {response.text}")

if __name__ == '__main__':
    # Replace with actual tech_proc_id
    test_materials_fetch(813346)
