#!/bin/bash
# Тест POST /rest/save на PSS-сервере — несколько операций подряд.
# Запуск: bash PSS-aiR/test_pss_save.sh
# Вывод: подробный лог каждого запроса (заголовки, тело, ответ, время).

PSS="http://localhost:7239"
DB="pss_moma_08_07_2025"
USER="Administrator"
LOG="PSS-aiR/test_pss_save.log"

> "$LOG"
log() { echo "$1" | tee -a "$LOG"; }

log "========================================"
log "  PSS /rest/save stress test"
log "  $(date '+%Y-%m-%d %H:%M:%S')"
log "========================================"
log ""

# 1. Connect
log "--- STEP 1: Connect ---"
log "GET $PSS/rest/connect/user=$USER&db=$DB"
CONNECT=$(curl -s -w "\n%{http_code} %{time_total}s" "$PSS/rest/connect/user=$USER&db=$DB")
HTTP_CODE=$(echo "$CONNECT" | tail -1 | awk '{print $1}')
TIME=$(echo "$CONNECT" | tail -1 | awk '{print $2}')
BODY=$(echo "$CONNECT" | sed '$d')
SK=$(echo "$BODY" | python -c "import sys,json; print(json.load(sys.stdin).get('session_key',''))" 2>/dev/null)
log "Response: HTTP $HTTP_CODE, time=$TIME"
log "Session key: ${SK:0:40}..."
log ""

if [ -z "$SK" ]; then
  log "ABORT: No session key"
  exit 1
fi

CREATED_IDS=()

# Function to do a save and log everything
do_save() {
  local STEP="$1"
  local DESC="$2"
  local PAYLOAD="$3"
  local TIMEOUT="${4:-30}"

  log "--- STEP $STEP: $DESC ---"
  log "POST $PSS/rest/save"
  log "Headers:"
  log "  X-APL-SessionKey: ${SK:0:40}..."
  log "  Content-Type: application/json"
  log "Body:"
  echo "$PAYLOAD" | python -m json.tool 2>/dev/null | tee -a "$LOG"
  log ""

  RESP=$(curl -s -w "\n---CURL_META---%{http_code} %{time_total}" \
    -X POST "$PSS/rest/save" \
    -H "X-APL-SessionKey: $SK" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" \
    --max-time "$TIMEOUT" 2>&1)

  META=$(echo "$RESP" | grep "^---CURL_META---" | sed 's/---CURL_META---//')
  RBODY=$(echo "$RESP" | grep -v "^---CURL_META---")
  HTTP=$(echo "$META" | awk '{print $1}')
  RTIME=$(echo "$META" | awk '{print $2}')

  if [ -z "$HTTP" ]; then
    log "Response: TIMEOUT or CONNECTION ERROR after ${TIMEOUT}s"
    log "Raw output: $(echo "$RESP" | head -3)"
    log "RESULT: FAIL (timeout)"
  else
    log "Response: HTTP $HTTP, time=${RTIME}s"
    echo "$RBODY" | python -m json.tool 2>/dev/null | head -20 | tee -a "$LOG"

    # Extract created IDs
    if [ "$HTTP" = "200" ]; then
      IDS=$(echo "$RBODY" | python -c "
import sys,json
try:
  d=json.load(sys.stdin)
  for inst in d.get('instances',[]):
    print(f\"  Created: type={inst.get('type')}, id={inst.get('id')}\")
except: pass
" 2>/dev/null)
      if [ -n "$IDS" ]; then
        log "$IDS"
        # Save IDs for cleanup
        for id in $(echo "$RBODY" | python -c "import sys,json; [print(i['id']) for i in json.load(sys.stdin).get('instances',[])]" 2>/dev/null); do
          CREATED_IDS+=("$id")
        done
      fi
      log "RESULT: PASS"
    else
      log "RESULT: FAIL (HTTP $HTTP)"
    fi
  fi
  log ""
}

# 2. Create product #1
do_save "2" "Create product #1 (SAVE-TEST-001)" '{
  "format":"apl_json_1",
  "dictionary":"apl_pss_a",
  "instances":[{
    "id":0, "index":0,
    "type":"apl_product_definition_formation",
    "attributes":{
      "formation_type":"part",
      "make_or_buy":"make",
      "of_product":{"id":0,"index":1,"type":"product","attributes":{"id":"SAVE-TEST-001","name":"SaveTest1"}}
    }
  }]
}'

# 3. Create product #2
do_save "3" "Create product #2 (SAVE-TEST-002)" '{
  "format":"apl_json_1",
  "dictionary":"apl_pss_a",
  "instances":[{
    "id":0, "index":0,
    "type":"apl_product_definition_formation",
    "attributes":{
      "formation_type":"assembly",
      "make_or_buy":"make",
      "of_product":{"id":0,"index":1,"type":"product","attributes":{"id":"SAVE-TEST-002","name":"SaveTest2"}}
    }
  }]
}'

# 4. Create product #3
do_save "4" "Create product #3 (SAVE-TEST-003)" '{
  "format":"apl_json_1",
  "dictionary":"apl_pss_a",
  "instances":[{
    "id":0, "index":0,
    "type":"apl_product_definition_formation",
    "attributes":{
      "formation_type":"material",
      "make_or_buy":"buy",
      "of_product":{"id":0,"index":1,"type":"product","attributes":{"id":"SAVE-TEST-003","name":"SaveTest3"}}
    }
  }]
}'

# 5. Update product #1 (need ID from step 2)
if [ ${#CREATED_IDS[@]} -ge 2 ]; then
  PDF_ID=${CREATED_IDS[0]}
  PROD_ID=${CREATED_IDS[1]}
  do_save "5" "Update product #1 name (id=$PROD_ID)" "{
    \"format\":\"apl_json_1\",
    \"dictionary\":\"apl_pss_a\",
    \"instances\":[{
      \"id\":$PROD_ID,
      \"type\":\"product\",
      \"attributes\":{\"name\":\"SaveTest1-EDITED\"}
    }]
  }"
else
  log "--- STEP 5: SKIP (no IDs from step 2) ---"
  log ""
fi

# 6. Create business process
do_save "6" "Create business process (SAVE-BP-001)" '{
  "format":"apl_json_1",
  "dictionary":"apl_pss_a",
  "instances":[{
    "id":0, "index":0,
    "type":"apl_business_process",
    "attributes":{
      "id":"SAVE-BP-001",
      "name":"SaveTestProcess"
    }
  }]
}'

# 7. Create characteristic value (on product #1)
if [ ${#CREATED_IDS[@]} -ge 2 ]; then
  PDF_ID=${CREATED_IDS[0]}
  do_save "7" "Create characteristic value (on pdf=$PDF_ID)" "{
    \"format\":\"apl_json_1\",
    \"dictionary\":\"apl_pss_a\",
    \"instances\":[{
      \"id\":0, \"index\":0,
      \"type\":\"apl_descriptive_characteristic_value\",
      \"attributes\":{
        \"val\":\"test-value-999\",
        \"item\":{\"id\":$PDF_ID,\"type\":\"apl_product_definition_formation\"}
      }
    }]
  }"
else
  log "--- STEP 7: SKIP (no PDF_ID) ---"
  log ""
fi

# 8. Delete created objects (cleanup)
if [ ${#CREATED_IDS[@]} -gt 0 ]; then
  IDS_STR=$(IFS=,; echo "${CREATED_IDS[*]}")
  log "--- STEP 8: Cleanup (DELETE ids: $IDS_STR) ---"
  log "DELETE $PSS/rest/$IDS_STR"
  RESP=$(curl -s -w "\n---CURL_META---%{http_code} %{time_total}" \
    -X DELETE "$PSS/rest/$IDS_STR" \
    -H "X-APL-SessionKey: $SK" \
    --max-time 30 2>&1)
  META=$(echo "$RESP" | grep "^---CURL_META---" | sed 's/---CURL_META---//')
  HTTP=$(echo "$META" | awk '{print $1}')
  RTIME=$(echo "$META" | awk '{print $2}')
  log "Response: HTTP $HTTP, time=${RTIME}s"
  if [ "$HTTP" = "204" ] || [ "$HTTP" = "200" ]; then
    log "RESULT: PASS"
  else
    RBODY=$(echo "$RESP" | grep -v "^---CURL_META---")
    log "Body: $(echo "$RBODY" | head -5)"
    log "RESULT: FAIL"
  fi
  log ""
fi

# Summary
log "========================================"
log "  SUMMARY"
log "========================================"
PASS_COUNT=$(grep -c "RESULT: PASS" "$LOG")
FAIL_COUNT=$(grep -c "RESULT: FAIL" "$LOG")
SKIP_COUNT=$(grep -c "STEP.*SKIP" "$LOG")
log "  PASS: $PASS_COUNT"
log "  FAIL: $FAIL_COUNT"
log "  SKIP: $SKIP_COUNT"
log "  Total created IDs: ${CREATED_IDS[*]}"
log "========================================"
log ""
log "Full log: $LOG"
