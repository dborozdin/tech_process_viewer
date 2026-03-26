"""
PSS REST API client for ILS Report Agent.
Adapted from tech_process_viewer/api/pss_api.py — minimal read-only subset.
"""

import json
import time
import logging
import requests

logger = logging.getLogger("ils.pss")


class PSSClient:
    """Client for the low-level PSS REST API (localhost:7239/rest)."""

    def __init__(self, rest_url: str):
        """
        Args:
            rest_url: Base REST URL, e.g. 'http://localhost:7239/rest'
        """
        self.rest_url = rest_url
        self.session_key = None
        self._api_log: list = []
        self._http = requests.Session()  # HTTP keep-alive

    @property
    def connected(self) -> bool:
        return self.session_key is not None

    def connect(self, db_name: str, user: str, password: str = "") -> str:
        """Connect to PSS database and obtain session key.

        Returns:
            Session key string.

        Raises:
            ConnectionError: If connection fails.
        """
        # Disconnect existing session first
        if self.session_key:
            try:
                self.disconnect()
            except Exception:
                pass

        creds = f"user={user}&db={db_name}"
        if password:
            creds += f"&password={password}"

        url = f"{self.rest_url}/connect/{creds}"
        logger.info(f"Connecting to PSS: {url}")

        try:
            resp = self._http.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise ConnectionError(f"Failed to connect to PSS: {e}") from e

        if 'session_key' not in data:
            raise ConnectionError(f"No session_key in response: {data}")

        self.session_key = data['session_key']
        logger.info(f"Connected. Session key: {self.session_key[:8]}...")
        return self.session_key

    def disconnect(self):
        """Disconnect from PSS database."""
        if not self.session_key:
            return
        try:
            self._http.get(
                f"{self.rest_url}/disconnect",
                headers=self._headers(),
                timeout=10
            )
        except Exception as e:
            logger.warning(f"Disconnect error: {e}")
        finally:
            self.session_key = None

    def _record_call(self, method: str, url: str, body: str | None,
                     elapsed: float, status_code: int, result_count: int | None,
                     error: str = None):
        entry = {
            "method": method,
            "url": url,
            "body": body,
            "elapsed_ms": round(elapsed * 1000, 1),
            "status_code": status_code,
            "result_count": result_count,
        }
        if error:
            entry["error"] = error
        self._api_log.append(entry)

    def flush_log(self) -> list:
        """Return and clear accumulated API call log."""
        log = self._api_log
        self._api_log = []
        return log

    def _headers(self) -> dict:
        if not self.session_key:
            raise RuntimeError("Not connected to PSS. Call connect() first.")
        return {
            "X-APL-SessionKey": self.session_key,
            "Content-Type": "application/json",
        }

    def query_apl(self, query: str, start: int = 0, size: int = 200,
                  all_attrs: bool = True) -> dict:
        """Execute APL query.

        Args:
            query: APL query string (e.g. SELECT NO_CASE ...)
            start: Pagination start offset.
            size: Max number of instances to return.
            all_attrs: Whether to return all attributes.

        Returns:
            Dict with keys: instances (list), count_all (int), portion_from (int).
        """
        attrs_param = "true" if all_attrs else "false"
        url = f"{self.rest_url}&start={start}&size={size}/query&all_attrs={attrs_param}"

        logger.debug(f"APL query: {query[:200]}...")
        t0 = time.perf_counter()

        try:
            resp = self._http.post(
                url, headers=self._headers(),
                data=query.encode("utf-8"),
                timeout=60
            )
            elapsed = time.perf_counter() - t0
            logger.debug(f"Query took {elapsed:.3f}s, status={resp.status_code}")

            if not resp.ok:
                error_text = resp.text[:1000].strip()
                logger.error(f"Query error: HTTP {resp.status_code}, body: {error_text}")
                self._record_call("POST", url, query, elapsed,
                                  resp.status_code, None,
                                  error=error_text)
                return {
                    'instances': [], 'count_all': 0, 'portion_from': start,
                    'error': f"HTTP {resp.status_code}: {error_text}",
                }

            result = json.loads(resp.text, strict=False)
            instances = result.get('instances', [])
            self._record_call("POST", url, query, elapsed,
                              resp.status_code, len(instances))
            return {
                'instances': instances,
                'count_all': result.get('count_all', 0),
                'portion_from': result.get('portion_from', start),
            }

        except requests.RequestException as e:
            elapsed = time.perf_counter() - t0
            logger.error(f"Query failed: {e}")
            self._record_call("POST", url, query, elapsed, 0, None,
                              error=str(e))
            return {
                'instances': [], 'count_all': 0, 'portion_from': start,
                'error': str(e),
            }

    def load_instances(self, entity_type: str, start: int = 0, size: int = 50,
                       all_attrs: bool = True) -> dict:
        """Load instances using optimized GET /load/ endpoint.

        Args:
            entity_type: Entity type name (e.g. 'organization').
            start: Pagination start offset.
            size: Number of instances to return.
            all_attrs: Whether to return all attributes.

        Returns:
            Dict with keys: instances, count_all, portion_from.
        """
        attrs = "true" if all_attrs else "false"
        url = f"{self.rest_url}&size={size}&start={start}/load/t=e&ent={entity_type}&all_attrs={attrs}"

        logger.debug(f"Loading {entity_type}, start={start}, size={size}")
        t0 = time.perf_counter()

        try:
            resp = self._http.get(url, headers=self._headers(), timeout=60)
            elapsed = time.perf_counter() - t0
            logger.debug(f"Load took {elapsed:.3f}s, status={resp.status_code}")

            if not resp.ok:
                logger.error(f"Load error: HTTP {resp.status_code}")
                resp.raise_for_status()

            result = json.loads(resp.text, strict=False)
            instances = result.get('instances', [])
            count_all = result.get('count_all', len(instances))
            portion_from = result.get('portion_from', start)

            # Handle PSS not respecting start parameter
            if portion_from == 0 and start > 0 and len(instances) > start:
                instances = instances[start:]
                portion_from = start

            if len(instances) > size:
                instances = instances[:size]

            self._record_call("GET", url, None, elapsed,
                              resp.status_code, len(instances))
            return {
                'instances': instances,
                'count_all': count_all,
                'portion_from': portion_from,
            }

        except requests.RequestException as e:
            logger.error(f"Load failed for {entity_type}: {e}")
            self._record_call("GET", url, None,
                              time.perf_counter() - t0, 0, None)
            return {'instances': [], 'count_all': 0, 'portion_from': start}

    def get_instance(self, sys_id: int, entity_type: str = None) -> dict | None:
        """Get a single instance by system ID.

        Returns:
            Instance dict or None if not found.
        """
        if entity_type:
            query = f"SELECT NO_CASE Ext_ FROM Ext_{{{entity_type}(.# = #{sys_id})}} END_SELECT"
        else:
            query = f"SELECT NO_CASE Ext_ FROM Ext_{{#{sys_id}}} END_SELECT"

        result = self.query_apl(query, size=1)
        instances = result.get('instances', [])
        return instances[0] if instances else None

    def count_instances(self, entity_type: str, filters: str = None) -> int:
        """Get count of instances for entity type.

        Args:
            entity_type: Entity type name.
            filters: Optional APL filter condition (e.g. '.name LIKE "test"').

        Returns:
            Number of matching instances.
        """
        if filters:
            query = f"SELECT NO_CASE Ext_ FROM Ext_{{{entity_type}({filters})}} END_SELECT"
        else:
            query = f"SELECT NO_CASE Ext_ FROM Ext_{{{entity_type}}} END_SELECT"

        result = self.query_apl(query, size=1, all_attrs=False)
        return result.get('count_all', 0)

    def query_instances(self, entity_type: str, filters: str = None,
                        start: int = 0, size: int = 100) -> list:
        """Query instances with optional filters.

        Args:
            entity_type: Entity type name.
            filters: APL filter condition string.
            start: Pagination offset.
            size: Max results.

        Returns:
            List of instance dicts.
        """
        if filters:
            query = f"SELECT NO_CASE Ext_ FROM Ext_{{{entity_type}({filters})}} END_SELECT"
        else:
            query = f"SELECT NO_CASE Ext_ FROM Ext_{{{entity_type}}} END_SELECT"

        result = self.query_apl(query, start=start, size=size)
        return result.get('instances', [])
