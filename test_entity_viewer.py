"""
Test script for Entity Viewer CRUD operations.
Default entity type: organization
"""

from api.pss_api import DatabaseAPI


def setup_api():
    """Connect to DB and return API instance."""
    server_port = 'http://localhost:7239'
    db = 'pss_moma_08_07_2025'
    user = 'Administrator'

    credentials = f'user={user}&db={db}'
    url_db_api = server_port + '/rest'
    api = DatabaseAPI(url_db_api, credentials)

    session_key = api.reconnect_db()
    if session_key is None:
        raise RuntimeError('Failed to connect to DB')

    print(f'Connected to DB. Session key: {session_key}')
    return api


def test_create_organization(api):
    """Create organization with id='TEST', name='TEST' and verify by reading."""
    print('\n=== TEST: Create organization ===')

    result = api.create_instance('organization', {
        'id': 'TEST',
        'name': 'TEST'
    })

    assert result is not None, 'create_instance returned None'

    sys_id = result.get('id')
    print(f'Created instance with system ID: {sys_id}')

    # Verify by reading
    found = api.get_instance(sys_id)
    assert found is not None, f'Instance {sys_id} not found after creation'

    attrs = found.get('attributes', {})
    assert attrs.get('id') == 'TEST', f'Expected id="TEST", got id="{attrs.get("id")}"'
    assert attrs.get('name') == 'TEST', f'Expected name="TEST", got name="{attrs.get("name")}"'

    print(f'Verified: id="{attrs["id"]}", name="{attrs["name"]}"')
    print('=== PASSED ===')
    return sys_id


def test_update_organization(api, sys_id):
    """Update organization attributes to id='TEST1', name='TEST1' and verify."""
    print('\n=== TEST: Update organization ===')

    result = api.update_instance(sys_id, 'organization', {
        'id': 'TEST1',
        'name': 'TEST1'
    })

    assert result is not None, 'update_instance returned None'
    print(f'Updated instance {sys_id}')

    # Verify by reading
    updated = api.get_instance(sys_id)
    assert updated is not None, f'Instance {sys_id} not found after update'

    attrs = updated.get('attributes', {})
    assert attrs.get('id') == 'TEST1', f'Expected id="TEST1", got id="{attrs.get("id")}"'
    assert attrs.get('name') == 'TEST1', f'Expected name="TEST1", got name="{attrs.get("name")}"'

    print(f'Verified: id="{attrs["id"]}", name="{attrs["name"]}"')
    print('=== PASSED ===')


def test_delete_organization(api, sys_id):
    """Delete the created organization (soft delete)."""
    print('\n=== TEST: Delete organization ===')

    success = api.delete_instance(sys_id, 'organization', soft_delete=True)
    assert success, f'delete_instance returned False for {sys_id}'

    print(f'Deleted instance {sys_id} (soft delete)')
    print('=== PASSED ===')


if __name__ == '__main__':
    api = setup_api()

    try:
        sys_id = test_create_organization(api)
        test_update_organization(api, sys_id)
        test_delete_organization(api, sys_id)
        print('\n=============================')
        print('All tests passed!')
        print('=============================')
    finally:
        api.disconnect_db()
