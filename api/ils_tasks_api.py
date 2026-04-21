"""
API for fetching ILS tasks (process charts / технологические карты)
linked to logistic structure components.

Link chain: component → apl_lss3_ls_obj_pc_link (ls_obj) → ils_process_chart (pc)
"""

import logging
from typing import Protocol, runtime_checkable

logger = logging.getLogger("ils.tasks")


@runtime_checkable
class APLQueryable(Protocol):
    """Minimal interface: execute APL query, return {instances, count_all}."""

    def query_apl(self, query: str, start: int = 0, size: int = 200,
                  all_attrs: bool = True) -> dict: ...


_PC_ATTRS = [
    "name", "id_mrbr", "id_mpd", "ATA",
    "type", "labour_full", "labour_unit",
    "description",
]


class ILSTasksAPI:
    """Fetches process charts (tasks) for logistic structure components."""

    PAGE_SIZE = 200

    def __init__(self, queryable):
        self._q = queryable

    def get_tasks(self, component_sys_id: int) -> dict:
        """Get all process charts (ils_process_chart) linked to a component.

        Finds apl_lss3_ls_obj_pc_link where ls_obj = component_sys_id,
        then resolves the pc reference to ils_process_chart.

        Returns:
            {"component_sys_id": N, "count": N, "tasks": [...]}
        """
        # 1. Find link objects
        q = (f"SELECT NO_CASE Ext_ FROM "
             f"Ext_{{apl_lss3_ls_obj_pc_link(.ls_obj = #{component_sys_id})}} "
             f"END_SELECT")

        result = self._q.query_apl(q, size=self.PAGE_SIZE)
        if result.get("error"):
            logger.warning("get_tasks query error: %s", result["error"])
            return {
                "component_sys_id": component_sys_id,
                "count": 0,
                "tasks": [],
                "error": result["error"],
            }

        links = result.get("instances", [])

        # 2. Extract pc references (ils_process_chart sys_ids)
        pc_ids = []
        for link in links:
            attrs = link.get("attributes", {})
            pc_ref = attrs.get("pc")
            if isinstance(pc_ref, dict) and "id" in pc_ref:
                pc_ids.append(pc_ref["id"])
            elif isinstance(pc_ref, (int, str)):
                pc_ids.append(int(pc_ref))

        if not pc_ids:
            return {
                "component_sys_id": component_sys_id,
                "count": 0,
                "tasks": [],
            }

        # 3. Batch-fetch ils_process_chart instances
        tasks = []
        BATCH = 50
        for i in range(0, len(pc_ids), BATCH):
            batch = pc_ids[i:i + BATCH]
            conditions = " OR ".join(f".# = #{sid}" for sid in batch)
            q2 = (f"SELECT NO_CASE Ext_ FROM "
                  f"Ext_{{ils_process_chart({conditions})}} END_SELECT")
            res = self._q.query_apl(q2, size=len(batch))
            for inst in res.get("instances", []):
                tasks.append(self._simplify_pc(inst))

        return {
            "component_sys_id": component_sys_id,
            "count": len(tasks),
            "tasks": tasks,
        }

    @staticmethod
    def _simplify_pc(instance: dict) -> dict:
        """Extract key attributes from ils_process_chart instance."""
        attrs = instance.get("attributes", {})
        result = {"sys_id": instance.get("id"), "type": instance.get("type")}
        for key in _PC_ATTRS:
            val = attrs.get(key)
            if val is None:
                continue
            if isinstance(val, dict) and "id" in val:
                ref_name = val.get("attributes", {}).get("name", "")
                result[key] = ref_name if ref_name else f"→#{val['id']}"
            elif isinstance(val, list):
                result[key] = f"[{len(val)} items]"
            elif val != "" and val != 0:
                result[key] = val
        return result
