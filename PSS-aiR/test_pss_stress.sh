#!/bin/bash
# Стресс-тест PSS REST API: последовательные POST /rest/save и DELETE.
# Цель: воспроизвести зависание/падение сервера.
# Подробный лог каждого запроса.

PSS="http://localhost:7239"
DB="pss_moma_08_07_2025"
LOG="PSS-aiR/test_pss_stress.log"
> "$LOG"

log() { echo "$1" | tee -a "$LOG"; }
logn() { echo -n "$1" | tee -a "$LOG"; }

log "================================================================"
log "  PSS REST API Stress Test"
log "  $(date '+%Y-%m-%d %H:%M:%S')"
log "  Server: $PSS"
log "================================================================"
log ""

# ── Connect ──
log ">>> CONNECT"
log "    GET $PSS/rest/connect/user=Administrator&db=$DB"
RESP=$(curl -s -w "\n%{http_code} %{time_total}" "$PSS/rest/connect/user=Administrator&db=$DB" 2>&1)
HTTP=$(echo "$RESP" | tail -1 | awk '{print $1}')
TIME=$(echo "$RESP" | tail -1 | awk '{print $2}')
BODY=$(echo "$RESP" | sed '$d')
SK=$(echo "$BODY" | python -c "import sys,json; print(json.load(sys.stdin).get('session_key',''))" 2>/dev/null)
log "    Status: $HTTP  Time: ${TIME}s"
log "    Session: ${SK:0:50}..."
log ""

if [ -z "$SK" ]; then
  log "ABORT: no session key"
  exit 1
fi

PASS=0
FAIL=0
TOTAL=0
ALL_IDS=()

do_request() {
  local METHOD="$1"
  local URL="$2"
  local DATA="$3"
  local DESC="$4"
  local TIMEOUT="${5:-30}"

  TOTAL=$((TOTAL + 1))
  log "--- #$TOTAL: $DESC ---"
  log "    $METHOD $URL"
  log "    Headers: X-APL-SessionKey: ${SK:0:30}...  Content-Type: application/json"

  if [ -n "$DATA" ]; then
    # Pretty-print body (compact)
    PRETTY=$(echo "$DATA" | python -m json.tool --compact 2>/dev/null || echo "$DATA")
    log "    Body: $PRETTY"
  fi

  local START_MS=$(date +%s%N)

  if [ "$METHOD" = "DELETE" ]; then
    RESP=$(curl -s -w "\n---META---%{http_code} %{time_total}" \
      -X DELETE "$URL" \
      -H "X-APL-SessionKey: $SK" \
      --max-time "$TIMEOUT" 2>&1)
  elif [ "$METHOD" = "POST" ]; then
    RESP=$(curl -s -w "\n---META---%{http_code} %{time_total}" \
      -X POST "$URL" \
      -H "X-APL-SessionKey: $SK" \
      -H "Content-Type: application/json" \
      -d "$DATA" \
      --max-time "$TIMEOUT" 2>&1)
  elif [ "$METHOD" = "GET" ]; then
    RESP=$(curl -s -w "\n---META---%{http_code} %{time_total}" \
      "$URL" \
      -H "X-APL-SessionKey: $SK" \
      --max-time "$TIMEOUT" 2>&1)
  fi

  META=$(echo "$RESP" | grep "^---META---" | sed 's/---META---//')
  RBODY=$(echo "$RESP" | grep -v "^---META---")
  HTTP=$(echo "$META" | awk '{print $1}')
  RTIME=$(echo "$META" | awk '{print $2}')

  if [ -z "$HTTP" ] || [ "$HTTP" = "000" ]; then
    log "    Response: TIMEOUT/CONNECTION ERROR (${TIMEOUT}s limit)"
    log "    Raw: $(echo "$RBODY" | head -2)"
    log "    >>> FAIL <<<"
    FAIL=$((FAIL + 1))
    log ""
    return 1
  fi

  log "    Response: HTTP $HTTP  Time: ${RTIME}s"

  # Show response body (truncated)
  RLEN=${#RBODY}
  if [ "$RLEN" -gt 500 ]; then
    log "    Body (${RLEN} chars, truncated):"
    echo "$RBODY" | python -m json.tool 2>/dev/null | head -15 | while IFS= read -r line; do log "      $line"; done
    log "      ..."
  elif [ "$RLEN" -gt 0 ]; then
    log "    Body:"
    echo "$RBODY" | python -m json.tool 2>/dev/null | while IFS= read -r line; do log "      $line"; done
  fi

  if [ "$HTTP" = "200" ] || [ "$HTTP" = "204" ]; then
    log "    >>> PASS <<<"
    PASS=$((PASS + 1))

    # Extract created IDs
    IDS=$(echo "$RBODY" | python -c "import sys,json
try:
  d=json.load(sys.stdin)
  for i in d.get('instances',[]): print(i['id'])
except: pass" 2>/dev/null)
    for id in $IDS; do
      ALL_IDS+=("$id")
    done
  else
    log "    >>> FAIL <<<"
    FAIL=$((FAIL + 1))
  fi
  log ""
  return 0
}

# ── Phase 1: Sequential Creates (10 products) ──
log "════════════════════════════════════════"
log "  PHASE 1: Sequential Creates (10 products)"
log "════════════════════════════════════════"
log ""

for i in $(seq 1 10); do
  do_request POST "$PSS/rest/save" \
    "{\"format\":\"apl_json_1\",\"dictionary\":\"apl_pss_a\",\"instances\":[{\"id\":0,\"index\":0,\"type\":\"apl_product_definition_formation\",\"attributes\":{\"formation_type\":\"part\",\"make_or_buy\":\"make\",\"of_product\":{\"id\":0,\"index\":1,\"type\":\"product\",\"attributes\":{\"id\":\"STRESS-$i\",\"name\":\"StressTest$i\"}}}}]}" \
    "Create product STRESS-$i"
  RET=$?
  if [ $RET -ne 0 ]; then
    log "!!! Server unreachable after product #$i — stopping Phase 1"
    break
  fi
done

# ── Phase 2: Sequential Updates ──
log "════════════════════════════════════════"
log "  PHASE 2: Sequential Updates"
log "════════════════════════════════════════"
log ""

# Update the product entities (odd indices = product IDs)
for i in $(seq 1 2 ${#ALL_IDS[@]}); do
  PID=${ALL_IDS[$i]}
  if [ -n "$PID" ]; then
    do_request POST "$PSS/rest/save" \
      "{\"format\":\"apl_json_1\",\"dictionary\":\"apl_pss_a\",\"instances\":[{\"id\":$PID,\"type\":\"product\",\"attributes\":{\"name\":\"StressEdited-$PID\"}}]}" \
      "Update product id=$PID"
    if [ $? -ne 0 ]; then
      log "!!! Server unreachable during update — stopping Phase 2"
      break
    fi
  fi
done

# ── Phase 3: Read between writes ──
log "════════════════════════════════════════"
log "  PHASE 3: Read between writes (query + save alternating)"
log "════════════════════════════════════════"
log ""

for i in $(seq 11 15); do
  # Query first
  do_request POST "$PSS/rest/query" \
    "SELECT NO_CASE Ext_ FROM Ext_{apl_folder} END_SELECT" \
    "Query folders (before create #$i)" 10

  # Then create
  do_request POST "$PSS/rest/save" \
    "{\"format\":\"apl_json_1\",\"dictionary\":\"apl_pss_a\",\"instances\":[{\"id\":0,\"index\":0,\"type\":\"apl_product_definition_formation\",\"attributes\":{\"formation_type\":\"assembly\",\"make_or_buy\":\"buy\",\"of_product\":{\"id\":0,\"index\":1,\"type\":\"product\",\"attributes\":{\"id\":\"STRESS-$i\",\"name\":\"StressMixed$i\"}}}}]}" \
    "Create product STRESS-$i"

  if [ $? -ne 0 ]; then
    log "!!! Server unreachable at mixed #$i — stopping Phase 3"
    break
  fi
done

# ── Phase 4: Deletes via POST /rest/save (type=null) ──
log "════════════════════════════════════════"
log "  PHASE 4: Deletes via POST /rest/save (type=null)"
log "════════════════════════════════════════"
log ""

for PID in "${ALL_IDS[@]}"; do
  if [ -n "$PID" ]; then
    do_request POST "$PSS/rest/save" \
      "{\"format\":\"apl_json_1\",\"dictionary\":\"apl_pss_a\",\"instances\":[{\"id\":$PID,\"type\":null}]}" \
      "Delete id=$PID (type=null)"
    if [ $? -ne 0 ]; then
      log "!!! Server unreachable during delete — stopping Phase 4"
      break
    fi
  fi
done

# ── Phase 5: Rapid fire (create + delete immediately) ──
log "════════════════════════════════════════"
log "  PHASE 5: Rapid create+delete cycles"
log "════════════════════════════════════════"
log ""

for i in $(seq 1 5); do
  do_request POST "$PSS/rest/save" \
    "{\"format\":\"apl_json_1\",\"dictionary\":\"apl_pss_a\",\"instances\":[{\"id\":0,\"index\":0,\"type\":\"product\",\"attributes\":{\"id\":\"RAPID-$i\",\"name\":\"Rapid$i\"}}]}" \
    "Rapid create RAPID-$i"

  if [ $? -ne 0 ]; then
    log "!!! Server unreachable at rapid #$i — stopping"
    break
  fi

  # Get last created ID
  LAST_ID=${ALL_IDS[-1]}
  if [ -n "$LAST_ID" ]; then
    do_request POST "$PSS/rest/save" \
      "{\"format\":\"apl_json_1\",\"dictionary\":\"apl_pss_a\",\"instances\":[{\"id\":$LAST_ID,\"type\":null}]}" \
      "Rapid delete id=$LAST_ID"
    if [ $? -ne 0 ]; then
      log "!!! Server unreachable at rapid delete #$i — stopping"
      break
    fi
  fi
done

# ── Check server alive ──
log "════════════════════════════════════════"
log "  FINAL CHECK: Is server still alive?"
log "════════════════════════════════════════"
log ""

ALIVE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$PSS/rest/dblist" 2>&1)
if [ "$ALIVE" = "200" ]; then
  log "Server: ALIVE (HTTP 200)"
else
  log "Server: DOWN (HTTP $ALIVE)"
fi

# ── Summary ──
log ""
log "================================================================"
log "  SUMMARY"
log "================================================================"
log "  Total requests: $TOTAL"
log "  PASS: $PASS"
log "  FAIL: $FAIL"
log "  Created IDs: ${#ALL_IDS[@]}"
log "  Server status: $([ "$ALIVE" = "200" ] && echo 'ALIVE' || echo 'DOWN')"
log "================================================================"
log ""
log "Full log: $LOG"
