"""PSS REST API Stress Test with Full Logging.

Цель: воспроизводимый тест save-операций PSS сервера.
Результат: детальный лог каждого запроса/ответа для передачи авторам сервера.

Предусловия:
  1. PSS сервер запущен: "C:\Program Files (x86)\PSS_MUI\AplNetTransportServTCP.exe" /p:7239
  2. БД восстановлена из бэкапа: copy pss_moma_08_07_2025_copy.aplb -> pss_moma_08_07_2025.aplb
  3. Вспомогательные файлы (.bak, .tmp, .crc, .aclst) удалены

Запуск: python PSS-aiR/test_pss_stress_log.py
"""

import os, sys, time, datetime, json, requests

# ── Configuration ──
PSS_PORT = 7239
PSS_BASE = f"http://localhost:{PSS_PORT}/rest"
DB_NAME = "pss_moma_08_07_2025"
USER = "Administrator"
PASSWORD = ""

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stress_test_log.txt")

session_key = None


def log(msg, also_print=True):
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[{ts}] {msg}"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    if also_print:
        print(line)


def pss_request(method, path, body=None, content_type=None):
    """Execute PSS REST request with full logging."""
    url = f"{PSS_BASE}/{path}"
    headers = {}
    if session_key:
        headers["X-APL-SessionKey"] = session_key
    if content_type:
        headers["Content-Type"] = content_type

    log(f">>> {method} {url}")
    for k, v in headers.items():
        log(f"    Header: {k}: {v}", also_print=False)
    if body:
        log(f"    Body ({len(body)} bytes): {body[:3000]}", also_print=False)

    t0 = time.time()
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=120)
        else:
            resp = requests.post(url, data=body.encode("utf-8") if body else b"", headers=headers, timeout=120)
        elapsed = (time.time() - t0) * 1000
    except Exception as e:
        elapsed = (time.time() - t0) * 1000
        log(f"<<< EXCEPTION after {elapsed:.0f}ms: {e}")
        return None

    log(f"<<< {resp.status_code} ({elapsed:.0f}ms) Content-Length: {len(resp.content)}")
    log(f"    Response: {resp.text[:3000]}", also_print=False)
    return resp


def main():
    global session_key

    # Clear log
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"{'='*70}\n")
        f.write(f"  PSS REST API Stress Test — Full Log\n")
        f.write(f"{'='*70}\n")
        f.write(f"Date:     {datetime.datetime.now().isoformat()}\n")
        f.write(f"Server:   http://localhost:{PSS_PORT}\n")
        f.write(f"Database: {DB_NAME}\n")
        f.write(f"User:     {USER}\n\n")

    results = []

    def record(name, ok, detail=""):
        status = "PASS" if ok else "FAIL"
        results.append((name, status, detail))
        log(f"  [{status}] {name}: {detail}")

    # ────────────────────────────────────────────
    # STEP 1: Check server
    # ────────────────────────────────────────────
    log("=" * 60)
    log("STEP 1: Check PSS server")
    log("=" * 60)

    resp = pss_request("GET", "dblist")
    if not resp or resp.status_code != 200:
        log("FATAL: PSS server not responding")
        return
    record("Server check (GET /rest/dblist)", True, f"OK, {len(resp.text)} bytes")

    # ────────────────────────────────────────────
    # STEP 2: Connect
    # ────────────────────────────────────────────
    log("\n" + "=" * 60)
    log("STEP 2: Connect to database")
    log("=" * 60)

    creds = f"user={USER}&db={DB_NAME}"
    if PASSWORD:
        creds += f"&password={PASSWORD}"
    resp = pss_request("GET", f"connect/{creds}")
    if not resp or resp.status_code != 200:
        log(f"FATAL: Connect failed")
        return

    data = resp.json()
    session_key = data.get("session_key", "")
    if not session_key:
        log(f"FATAL: No session_key. Response: {json.dumps(data, ensure_ascii=False, indent=2)[:500]}")
        return
    record("Connect", True, f"session_key={session_key[:20]}...")
    log(f"Full session_key: {session_key}")

    # ────────────────────────────────────────────
    # STEP 3: Read test (POST /rest/query with APL)
    # ────────────────────────────────────────────
    log("\n" + "=" * 60)
    log("STEP 3: Read operations (POST /rest/query)")
    log("=" * 60)

    # Query folders
    query_folders = 'SELECT Ext_ FROM Ext_{apl_folder} END_SELECT'
    resp = pss_request("POST", "query", query_folders)
    folders_ok = resp is not None and resp.status_code == 200
    count = 0
    if folders_ok:
        try:
            count = resp.json().get("count_all", 0)
        except:
            pass
    record("READ: query apl_folder", folders_ok, f"status={resp.status_code if resp else 'N/A'}, count={count}")

    # Query products
    query_products = 'SELECT Ext_ FROM Ext_{apl_product_definition_formation} END_SELECT'
    resp = pss_request("POST", "query", query_products)
    products_ok = resp is not None and resp.status_code == 200
    count = 0
    if products_ok:
        try:
            count = resp.json().get("count_all", 0)
        except:
            pass
    record("READ: query products (PDF)", products_ok, f"status={resp.status_code if resp else 'N/A'}, count={count}")

    # ────────────────────────────────────────────
    # STEP 4: Create product (POST /rest/save)
    # ────────────────────────────────────────────
    log("\n" + "=" * 60)
    log("STEP 4: Create product via POST /rest/save")
    log("=" * 60)

    # Exact format used by pss_products_api.py
    save_body = json.dumps({
        "format": "apl_json_1",
        "dictionary": "apl_pss_a",
        "instances": [{
            "id": 0,
            "index": 0,
            "type": "apl_product_definition_formation",
            "attributes": {
                "formation_type": "1",
                "make_or_buy": "1",
                "of_product": {
                    "id": 0,
                    "index": 1,
                    "type": "product",
                    "attributes": {
                        "id": "STRESS-TEST-001",
                        "name": "StressTestProduct"
                    }
                }
            }
        }]
    }, ensure_ascii=False)

    log(f"Save payload (pretty):")
    log(json.dumps(json.loads(save_body), indent=2, ensure_ascii=False), also_print=False)

    resp = pss_request("POST", "save", save_body, "application/json")
    save1_ok = False
    save1_detail = ""
    product_id = None

    if resp:
        if resp.status_code == 200:
            try:
                rdata = resp.json()
                instances = rdata.get("instances", [])
                for inst in instances:
                    if inst.get("type") == "apl_product_definition_formation":
                        product_id = inst.get("id")
                if product_id:
                    save1_ok = True
                    save1_detail = f"product_id={product_id}"
                else:
                    save1_detail = f"no product_id in response: {resp.text[:300]}"
            except Exception as e:
                save1_detail = f"JSON parse error: {e}, body: {resp.text[:300]}"
        else:
            save1_detail = f"HTTP {resp.status_code} ({resp.elapsed.total_seconds():.1f}s): {resp.text[:300]}"
    else:
        save1_detail = "no response (timeout?)"

    record("SAVE 1: Create product", save1_ok, save1_detail)

    if not save1_ok:
        log("\n" + "!" * 60)
        log("SAVE FAILED — stopping write tests")
        log("!" * 60)
        pss_request("GET", "disconnect")
        print_summary(results)
        return

    # ────────────────────────────────────────────
    # STEP 5: Verify created product
    # ────────────────────────────────────────────
    log("\n" + "=" * 60)
    log("STEP 5: Verify created product via query")
    log("=" * 60)

    # Wait for DB indexing
    log("    Waiting 2 seconds for DB indexing...")
    time.sleep(2)
    
    # Try multiple query approaches
    query_verify1 = 'SELECT Ext_ FROM Ext_{apl_product_definition_formation(.of_product->product.id = "STRESS-TEST-001")} END_SELECT'
    query_verify2 = 'SELECT Ext_.of_product FROM Ext_{apl_product_definition_formation(.id="' + str(product_id) + '")} END_SELECT'
    
    found = False
    detail = ""
    
    for i, query in enumerate([query_verify1, query_verify2]):
        log(f"    Try query {i+1}: {query[:80]}...")
        resp = pss_request("POST", "query", query)
        if resp and resp.status_code == 200:
            try:
                data = resp.json()
                instances = data.get("instances", [])
                for inst in instances:
                    attrs = inst.get("attributes", {})
                    # Check if this is the product we're looking for
                    if "of_product" in attrs:
                        of_product = attrs["of_product"]
                        if isinstance(of_product, dict) and "attributes" in of_product:
                            product_attrs = of_product["attributes"]
                            if product_attrs.get("id") == "STRESS-TEST-001":
                                found = True
                                detail = f"found with query {i+1}"
                                break
                    # Also check if the formation itself has an id attribute
                    if attrs.get("id") == "STRESS-TEST-001":
                        found = True
                        detail = f"found with query {i+1}"
                        break
                if found:
                    break
                else:
                    detail = f"not in response (query {i+1})"
            except Exception as e:
                detail = f"JSON parse error: {e} (query {i+1})"
        else:
            detail = f"HTTP {resp.status_code if resp else 'N/A'} (query {i+1})"
    
    record("READ: verify STRESS-TEST-001", found, f"found={found}, {detail}")

    # ────────────────────────────────────────────
    # STEP 6: Update product name
    # ────────────────────────────────────────────
    log("\n" + "=" * 60)
    log("STEP 6: Update product via POST /rest/save")
    log("=" * 60)

    # Simplified approach: Update the product directly using the formation ID
    # Based on PSS API documentation, we can update the product through formation
    # Wait a bit for consistency
    time.sleep(1)
    
    # Try approach 1: Update product name through formation
    update_body1 = json.dumps({
        "format": "apl_json_1",
        "dictionary": "apl_pss_a",
        "instances": [{
            "id": product_id,
            "type": "apl_product_definition_formation",
            "attributes": {
                "of_product": {
                    "type": "product",
                    "attributes": {
                        "name": "StressTestProduct_Updated"
                    }
                }
            }
        }]
    }, ensure_ascii=False)
    
    log("    Trying approach 1: Update through formation...")
    resp1 = pss_request("POST", "save", update_body1, "application/json")
    
    if resp1 and resp1.status_code == 200:
        save2_ok = True
        save2_detail = f"HTTP {resp1.status_code}: updated via formation"
    else:
        # Try approach 2: Load the formation to get product ID, then update product directly
        log("    Approach 1 failed, trying approach 2...")
        time.sleep(1)
        
        # Load the formation to get product reference
        load_resp = pss_request("GET", f"i={product_id}")
        product_instance_id = None
        
        if load_resp and load_resp.status_code == 200:
            try:
                data = load_resp.json()
                instances = data.get("instances", [])
                for inst in instances:
                    attrs = inst.get("attributes", {})
                    if "of_product" in attrs and attrs["of_product"]:
                        product_instance_id = attrs["of_product"].get("id")
                        break
            except:
                pass
        
        if product_instance_id:
            update_body2 = json.dumps({
                "format": "apl_json_1",
                "dictionary": "apl_pss_a",
                "instances": [{
                    "id": product_instance_id,
                    "type": "product",
                    "attributes": {
                        "name": "StressTestProduct_Updated"
                    }
                }]
            }, ensure_ascii=False)
            
            resp2 = pss_request("POST", "save", update_body2, "application/json")
            save2_ok = resp2 is not None and resp2.status_code == 200
            save2_detail = f"HTTP {resp2.status_code if resp2 else 'N/A'}: updated product directly (id={product_instance_id})"
        else:
            save2_ok = False
            save2_detail = "Could not get product instance ID"
    
    record("SAVE 2: Update product name", save2_ok, save2_detail[:200])

    # ────────────────────────────────────────────
    # STEP 7: Create second product
    # ────────────────────────────────────────────
    log("\n" + "=" * 60)
    log("STEP 7: Create second product")
    log("=" * 60)

    save3_body = json.dumps({
        "format": "apl_json_1",
        "dictionary": "apl_pss_a",
        "instances": [{
            "id": 0,
            "index": 0,
            "type": "apl_product_definition_formation",
            "attributes": {
                "formation_type": "2",
                "make_or_buy": "1",
                "of_product": {
                    "id": 0,
                    "index": 1,
                    "type": "product",
                    "attributes": {
                        "id": "STRESS-TEST-002",
                        "name": "StressTestProduct2"
                    }
                }
            }
        }]
    }, ensure_ascii=False)

    resp = pss_request("POST", "save", save3_body, "application/json")
    save3_ok = resp is not None and resp.status_code == 200
    product2_id = None
    if save3_ok:
        try:
            for inst in resp.json().get("instances", []):
                if inst.get("type") == "apl_product_definition_formation":
                    product2_id = inst.get("id")
        except:
            pass
    record("SAVE 3: Create product 2", save3_ok,
           f"product2_id={product2_id}" if save3_ok else f"HTTP {resp.status_code if resp else 'N/A'}: {resp.text[:200] if resp else ''}")

    # ────────────────────────────────────────────
    # STEP 8: Delete first product
    # ────────────────────────────────────────────
    log("\n" + "=" * 60)
    log("STEP 8: Delete product via POST /rest/save (type=null)")
    log("=" * 60)

    delete_body = json.dumps({
        "format": "apl_json_1",
        "dictionary": "apl_pss_a",
        "instances": [{
            "id": product_id,
            "index": product_id,
            "type": None
        }]
    }, ensure_ascii=False)

    resp = pss_request("POST", "save", delete_body, "application/json")
    save4_ok = resp is not None and resp.status_code == 200
    record("SAVE 4: Delete product 1", save4_ok,
           f"HTTP {resp.status_code if resp else 'N/A'}: {resp.text[:200] if resp else ''}")

    # ────────────────────────────────────────────
    # STEP 9: Rapid sequential creates (x3)
    # ────────────────────────────────────────────
    log("\n" + "=" * 60)
    log("STEP 9: Rapid sequential creates (3x)")
    log("=" * 60)

    for i in range(3):
        body = json.dumps({
            "format": "apl_json_1",
            "dictionary": "apl_pss_a",
            "instances": [{
                "id": 0,
                "index": 0,
                "type": "apl_product_definition_formation",
                "attributes": {
                    "formation_type": "1",
                    "make_or_buy": "1",
                    "of_product": {
                        "id": 0,
                        "index": 1,
                        "type": "product",
                        "attributes": {
                            "id": f"STRESS-RAPID-{i+1:03d}",
                            "name": f"RapidTest_{i+1}"
                        }
                    }
                }
            }]
        }, ensure_ascii=False)

        resp = pss_request("POST", "save", body, "application/json")
        ok = resp is not None and resp.status_code == 200
        detail = f"HTTP {resp.status_code}" if resp else "no response"
        if resp and not ok:
            detail += f": {resp.text[:200]}"
        record(f"SAVE {5+i}: Rapid create #{i+1}", ok, detail)
        if not ok:
            log(f"Rapid create #{i+1} FAILED — stopping")
            break
        time.sleep(0.5)

    # ────────────────────────────────────────────
    # STEP 10: Verify all created products
    # ────────────────────────────────────────────
    log("\n" + "=" * 60)
    log("STEP 10: Final verification — count all STRESS-* products")
    log("=" * 60)

    query_all = 'SELECT Ext_ FROM Ext_{apl_product_definition_formation(.of_product->product.id LIKE "STRESS")} END_SELECT'
    resp = pss_request("POST", "query", query_all)
    if resp and resp.status_code == 200:
        try:
            count = resp.json().get("count_all", 0)
        except:
            count = "?"
        record("READ: count STRESS-* products", True, f"count={count}")
    else:
        record("READ: count STRESS-* products", False, f"HTTP {resp.status_code if resp else 'N/A'}")

    # ────────────────────────────────────────────
    # STEP 11: Disconnect
    # ────────────────────────────────────────────
    log("\n" + "=" * 60)
    log("STEP 11: Disconnect")
    log("=" * 60)

    resp = pss_request("GET", "disconnect")
    record("Disconnect", resp is not None and resp.status_code in (200, 204),
           f"HTTP {resp.status_code if resp else 'N/A'}")

    # ── Summary ──
    print_summary(results)


def print_summary(results):
    log("\n" + "=" * 60)
    log("  RESULTS SUMMARY")
    log("=" * 60)
    for name, status, detail in results:
        log(f"  [{status:4}] {name:45} {detail[:80]}")
    passed = sum(1 for _, s, _ in results if s == "PASS")
    total = len(results)
    log(f"\n  {passed}/{total} PASS")
    log(f"\nDone at {datetime.datetime.now()}")
    log(f"Full log: {LOG_FILE}")


if __name__ == "__main__":
    main()
