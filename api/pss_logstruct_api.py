"""
High-level API for fetching ILS Logistic Structure trees from PSS database.

Works with both PSSClient (ILS agent) and DatabaseAPI (main app) via a
unified query interface.
"""

import logging
from typing import Protocol, runtime_checkable

logger = logging.getLogger("ils.logstruct")


# ---------------------------------------------------------------------------
# Unified query interface — adapts PSSClient and DatabaseAPI
# ---------------------------------------------------------------------------

@runtime_checkable
class APLQueryable(Protocol):
    """Minimal interface: execute APL query, return {instances, count_all}."""

    def query_apl(self, query: str, start: int = 0, size: int = 200,
                  all_attrs: bool = True) -> dict: ...


class DatabaseAPIAdapter:
    """Wraps legacy DatabaseAPI to match APLQueryable interface."""

    def __init__(self, db_api):
        self._db = db_api

    def query_apl(self, query: str, start: int = 0, size: int = 200,
                  all_attrs: bool = True) -> dict:
        attrs = "true" if all_attrs else "false"
        url = (f"{self._db.URL_DB_API}&start={start}&size={size}"
               f"/query&all_attrs={attrs}")
        result = self._db.query_apl(query, url=url)
        if result is None:
            return {"instances": [], "count_all": 0, "error": "Query failed"}
        return result


# ---------------------------------------------------------------------------
# Key attributes to extract (keep result compact for LLM context)
# ---------------------------------------------------------------------------

_COMPONENT_ATTRS = [
    "id", "name_rus", "name_eng", "descr_rus",
    "class", "type", "kind", "category",
    "maintainable", "repairabilty", "recommend_as_part",
    "is_standard", "is_fi", "spec_maint",
    "weight", "mtbf_calc", "mtbf_fact", "mtbur_calc",
    "essentiality_code", "short_name",
]

_ELEMENT_ATTRS = [
    "lcn", "name_rus", "name_eng", "descr_rus",
    "element_type", "logistic_type",
    "count_in_node", "position", "sns", "group",
    "guid",
]


# ---------------------------------------------------------------------------
# LogStructAPI
# ---------------------------------------------------------------------------

class LogStructAPI:
    """Fetches and assembles the logistic structure tree for a component."""

    # Safety limits
    MAX_ELEMENTS = 500
    PAGE_SIZE = 200

    def __init__(self, queryable):
        """Accept any object with query_apl(query, start, size, all_attrs)->dict.

        Works directly with PSSClient, or wrap DatabaseAPI via DatabaseAPIAdapter.
        """
        if not isinstance(queryable, APLQueryable):
            # Auto-wrap DatabaseAPI if it has URL_DB_API
            if hasattr(queryable, "URL_DB_API"):
                queryable = DatabaseAPIAdapter(queryable)
            else:
                raise TypeError(
                    f"Expected APLQueryable or DatabaseAPI, got {type(queryable)}"
                )
        self._q = queryable

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_logistic_structure(self, component_designation: str = "",
                               max_depth: int = 10,
                               sys_id: int = None) -> dict:
        """Fetch the full logistic structure tree for a component.

        Args:
            component_designation: Component id or name_rus to search for.
            max_depth: Maximum tree depth to descend.
            sys_id: Direct sys_id of the component (from a previous query).
                    If provided, component_designation is ignored.

        Returns:
            {
                root_component: {sys_id, id, name_rus, ...},
                total_elements: int,
                tree: [{depth, lcn, name_rus, element_type, component, count_in_node, ...}],
                warning: str | absent,
            }
        """
        # 1. Find root component
        root = self._find_component(component_designation, sys_id=sys_id)
        if root is None:
            searched = f"sys_id={sys_id}" if sys_id else f"'{component_designation}'"
            return {
                "error": f"Компонент {searched} не найден",
                "hint": "sys_id должен быть взят из поля sys_id результата предыдущего "
                        "query_instances, а НЕ придуман. Вызови: "
                        "query_instances('apl_lss3_component', '.is_fi = true') "
                        "и используй sys_id из ответа.",
            }

        root_info = self._simplify_component(root)

        # 2. Build tree recursively
        tree = []
        self._build_tree(
            parent_sys_id=root_info["sys_id"],
            by_component=True,
            depth=0,
            max_depth=max_depth,
            tree=tree,
        )

        # 3. Batch-resolve child_component references
        comp_ids = set()
        for node in tree:
            cid = node.pop("_child_component_id", None)
            if cid:
                comp_ids.add(cid)
                node["_cid"] = cid

        comp_map = self._resolve_components(list(comp_ids)) if comp_ids else {}

        for node in tree:
            cid = node.pop("_cid", None)
            if cid and cid in comp_map:
                node["component"] = comp_map[cid]

        result = {
            "root_component": root_info,
            "total_elements": len(tree),
            "tree": tree,
        }
        if len(tree) >= self.MAX_ELEMENTS:
            result["warning"] = (
                f"Дерево обрезано до {self.MAX_ELEMENTS} элементов. "
                "Уточните запрос или уменьшите max_depth."
            )
        return result

    # ------------------------------------------------------------------
    # Component search
    # ------------------------------------------------------------------

    def _find_component(self, designation: str = "",
                        sys_id: int = None) -> dict | None:
        """Find a component by sys_id, id (exact), or name_rus (LIKE)."""
        # 1. Direct lookup by sys_id (most reliable)
        if sys_id is not None:
            q = (f'SELECT NO_CASE Ext_ FROM '
                 f'Ext_{{apl_lss3_component(.# = #{sys_id})}} END_SELECT')
            result = self._q.query_apl(q, size=1)
            instances = result.get("instances", [])
            if instances:
                return instances[0]
            logger.warning(f"sys_id={sys_id} not found, falling back to designation")
            # Fall through to designation search

        if not designation:
            return None

        # 2. Try exact match on id
        q = (f'SELECT NO_CASE Ext_ FROM '
             f'Ext_{{apl_lss3_component(.id = "{designation}")}} END_SELECT')
        result = self._q.query_apl(q, size=5)
        instances = result.get("instances", [])
        if instances:
            return instances[0]

        # 3. Try name_rus LIKE
        q = (f'SELECT NO_CASE Ext_ FROM '
             f'Ext_{{apl_lss3_component(.name_rus LIKE "{designation}")}} END_SELECT')
        result = self._q.query_apl(q, size=5)
        instances = result.get("instances", [])
        if instances:
            return instances[0]

        return None

    # ------------------------------------------------------------------
    # Tree building
    # ------------------------------------------------------------------

    def _build_tree(self, parent_sys_id: int, by_component: bool,
                    depth: int, max_depth: int, tree: list):
        """Recursively fetch logistic elements and build flat tree with depth."""
        if depth >= max_depth or len(tree) >= self.MAX_ELEMENTS:
            return

        elements = self._fetch_child_elements(parent_sys_id, by_component)

        for el in elements:
            if len(tree) >= self.MAX_ELEMENTS:
                break

            # Skip zone_link elements (zones are not part of logistic structure)
            attrs = el.get("attributes", {})
            el_type = attrs.get("element_type")
            if isinstance(el_type, str) and el_type == "zone_link":
                continue
            # element_type may be a classifier reference
            if isinstance(el_type, dict):
                el_type_name = el_type.get("attributes", {}).get("name", "")
                if "zone" in el_type_name.lower():
                    continue

            node = self._simplify_element(el)
            node["depth"] = depth

            # Extract child_component sys_id for batch resolution later
            attrs = el.get("attributes", {})
            child_comp = attrs.get("child_component")
            if isinstance(child_comp, dict) and "id" in child_comp:
                node["_child_component_id"] = child_comp["id"]

            tree.append(node)

            # Recurse: children are linked via parent_component of the child_component
            child_comp = attrs.get("child_component")
            if isinstance(child_comp, dict) and "id" in child_comp:
                child_comp_type = child_comp.get("type", "")
                # Only recurse into components, not zones
                if "zone" not in child_comp_type:
                    self._build_tree(
                        parent_sys_id=child_comp["id"],
                        by_component=True,
                        depth=depth + 1,
                        max_depth=max_depth,
                        tree=tree,
                    )

    def _fetch_child_elements(self, parent_sys_id: int,
                              by_component: bool = True) -> list:
        """Fetch logistic elements under a parent (paginated).

        Args:
            parent_sys_id: sys_id of parent.
            by_component: If True, search by parent_component; else by parent_element.
        """
        ref_attr = "parent_component" if by_component else "parent_element"
        q = (f"SELECT NO_CASE Ext2 FROM Ext_{{#{parent_sys_id}}} "
             f"Ext2{{apl_lss3_logistic_element(.{ref_attr} IN #Ext_)}} END_SELECT")

        all_instances = []
        start = 0
        while True:
            result = self._q.query_apl(q, start=start, size=self.PAGE_SIZE)
            if result.get("error"):
                logger.warning(f"Query error fetching children of #{parent_sys_id}: "
                               f"{result['error']}")
                break
            instances = result.get("instances", [])
            all_instances.extend(instances)
            count_all = result.get("count_all", 0)
            if len(all_instances) >= count_all or len(instances) < self.PAGE_SIZE:
                break
            start += self.PAGE_SIZE

        return all_instances

    # ------------------------------------------------------------------
    # Batch component resolution
    # ------------------------------------------------------------------

    def _resolve_components(self, sys_ids: list[int]) -> dict[int, dict]:
        """Fetch components by sys_ids individually, return {sys_id: simplified_dict}."""
        result_map = {}
        for sid in sys_ids:
            q = (f"SELECT NO_CASE Ext_ FROM "
                 f"Ext_{{apl_lss3_component(.# = #{sid})}} END_SELECT")
            res = self._q.query_apl(q, size=1)
            for inst in res.get("instances", []):
                inst_id = inst.get("id")
                if inst_id:
                    result_map[inst_id] = self._simplify_component(inst)
        return result_map

    # ------------------------------------------------------------------
    # Simplification (extract key attributes, keep compact)
    # ------------------------------------------------------------------

    @staticmethod
    def _simplify_component(instance: dict) -> dict:
        """Extract key attributes from a raw PSS component instance."""
        attrs = instance.get("attributes", {})
        result = {"sys_id": instance.get("id"), "type": instance.get("type")}
        for key in _COMPONENT_ATTRS:
            val = attrs.get(key)
            if val is None:
                continue
            if isinstance(val, dict) and "id" in val:
                # Reference — show as readable string
                ref_name = val.get("attributes", {}).get("name", "")
                if ref_name:
                    result[key] = ref_name
                else:
                    result[key] = f"→#{val['id']} ({val.get('type', '')})"
            elif isinstance(val, list):
                result[key] = f"[{len(val)} items]"
            elif val != "" and val != 0 and val is not False:
                result[key] = val
            elif key in ("maintainable", "repairabilty", "recommend_as_part",
                         "is_standard", "is_fi", "spec_maint"):
                # Keep boolean false values for important flags
                result[key] = val
        return result

    @staticmethod
    def _simplify_element(instance: dict) -> dict:
        """Extract key attributes from a raw PSS logistic element instance."""
        attrs = instance.get("attributes", {})
        result = {"sys_id": instance.get("id")}
        for key in _ELEMENT_ATTRS:
            val = attrs.get(key)
            if val is None:
                continue
            if isinstance(val, dict) and "id" in val:
                ref_name = val.get("attributes", {}).get("name", "")
                if ref_name:
                    result[key] = ref_name
                else:
                    result[key] = f"→#{val['id']} ({val.get('type', '')})"
            elif isinstance(val, list):
                result[key] = f"[{len(val)} items]"
            elif val != "" and val != 0:
                result[key] = val
        return result
