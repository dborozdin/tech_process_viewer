"""
PSS data schema: dictionary parser + HTML entity descriptions.
Provides entity/attribute metadata and Russian-language descriptions for agent tools.
"""

import os
import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger("ils.schema")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AttributeInfo:
    id: int
    entity_id: int
    name: str
    datatype: str
    mandatory: bool
    description: str = ""

    def is_reference(self) -> bool:
        return 'instance' in self.datatype.lower() or 'aggr' in self.datatype.lower()

    def get_reference_entity_id(self) -> Optional[int]:
        m = re.search(r'(\d+)', self.datatype)
        return int(m.group(1)) if m and self.is_reference() else None

    def is_aggregate(self) -> bool:
        return 'aggr' in self.datatype.lower() or 'aggregate' in self.datatype.lower()


@dataclass
class EntityInfo:
    id: int
    name: str
    supertype_id: Optional[int] = None
    attributes: List[AttributeInfo] = field(default_factory=list)
    section: str = ""  # e.g. "LSS- 1. Анализ ИЛС"
    description: str = ""  # Russian description from HTML

    def get_all_attributes(self, entities: Dict[int, 'EntityInfo']) -> List[AttributeInfo]:
        """Get own + inherited attributes."""
        result = list(self.attributes)
        current = self.supertype_id
        while current and current in entities:
            sup = entities[current]
            result.extend(sup.attributes)
            current = sup.supertype_id
        return result


# ---------------------------------------------------------------------------
# Dictionary file parser (from apl_pss_a.dict)
# ---------------------------------------------------------------------------

KNOWN_TYPE_KEYWORDS = {
    'string', 'integer', 'real', 'float', 'boolean',
    'enumeration', 'number', 'instance', 'aggr', 'select',
    'aggregate', 'list', 'set', 'bag', 'identifier', 'label', 'text',
}


def _parse_dict_file(path: str) -> Dict[int, EntityInfo]:
    """Parse apl_pss_a.dict and return {entity_id: EntityInfo}."""
    entities: Dict[int, EntityInfo] = {}

    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        if line.startswith('E '):
            parts = line.split()
            if len(parts) < 3:
                continue
            eid = int(parts[1])
            ename = parts[2]
            supertype = None
            if len(parts) > 3:
                if parts[3] == 'N':
                    supertype = None
                elif parts[3] == 'Y':
                    supertype = int(parts[4]) if len(parts) > 4 else None
                else:
                    try:
                        supertype = int(parts[3])
                    except ValueError:
                        pass
            entities[eid] = EntityInfo(id=eid, name=ename, supertype_id=supertype)

        elif line.startswith('A '):
            parts = line.split(maxsplit=6)
            if len(parts) < 7 or parts[2] != 'e':
                continue
            attr_id = int(parts[1])
            entity_id = int(parts[3])
            mandatory = parts[4] == 'F'
            raw = parts[6] if len(parts) > 6 else 'unknown'

            # Split name from datatype
            words = raw.split()
            if len(words) >= 2 and words[0].lower() not in KNOWN_TYPE_KEYWORDS:
                attr_name = words[0]
                dtype = ' '.join(words[1:])
            else:
                attr_name = f"attr_{attr_id}"
                dtype = raw

            if entity_id in entities:
                entities[entity_id].attributes.append(AttributeInfo(
                    id=attr_id, entity_id=entity_id, name=attr_name,
                    datatype=dtype, mandatory=mandatory,
                ))

    return entities


# ---------------------------------------------------------------------------
# HTML descriptions parser (from apl_pss_a_1419_data.htm)
# ---------------------------------------------------------------------------

def _parse_html_descriptions(html_path: str, entities: Dict[int, EntityInfo]):
    """
    Enrich entities with section names and attribute descriptions
    from the HTML schema documentation file.
    """
    if not os.path.exists(html_path):
        logger.warning(f"HTML schema file not found: {html_path}")
        return

    with open(html_path, 'r', encoding='windows-1251') as f:
        text = f.read()

    # Parse section headers: <H2><a NAME="...">...</a>SECTION_NAME</H2>
    sections = []
    for m in re.finditer(r'<H2><a NAME\s*=\s*"[^"]*"></a>([^<]+)</H2>', text):
        sections.append((m.start(), m.group(1).strip()))

    def _find_section(pos: int) -> str:
        section_name = ""
        for sec_pos, sec_name in sections:
            if sec_pos <= pos:
                section_name = sec_name
            else:
                break
        return section_name

    # Parse entity blocks: <a NAME="eID"></a><H4><b>#ID name</b></H4> ... </table>
    entity_pattern = re.compile(
        r'<a NAME\s*=\s*"e(\d+)"></a><H4><b>#\d+\s+([^<]+)</b></H4>(.*?)</table>',
        re.DOTALL
    )

    for m in entity_pattern.finditer(text):
        eid = int(m.group(1))
        entity_display_name = m.group(2).strip()
        block = m.group(3)

        if eid not in entities:
            continue

        entity = entities[eid]
        entity.section = _find_section(m.start())

        # If entity display name differs from dict name, store as description
        if entity_display_name != entity.name:
            entity.description = entity_display_name

        # Parse attribute descriptions from table rows
        # Format: <td>#ID</td><td>attr_name</td><td>mandatory</td><td>type</td><td>DESCRIPTION</td><td>api_note</td>
        row_pattern = re.compile(
            r'<tr><td>#(\d+)</td>'
            r'<td>([^<]*)</td>'           # name
            r'<td[^>]*>[^<]*</td>'        # mandatory
            r'<td>([^<]*(?:<a[^>]*>[^<]*</a>)?[^<]*)</td>'  # type (may have links)
            r'<td>([^<]*)</td>'           # DESCRIPTION
            r'<td>([^<]*)</td></tr>'      # API note
        )
        for row in row_pattern.finditer(block):
            attr_id = int(row.group(1))
            desc = row.group(4).strip()
            if desc:
                for attr in entity.attributes:
                    if attr.id == attr_id:
                        attr.description = desc
                        break


# ---------------------------------------------------------------------------
# Schema — main interface
# ---------------------------------------------------------------------------

class Schema:
    """Unified access to PSS data schema: entities, attributes, descriptions."""

    def __init__(self, dict_path: str, html_path: str = None):
        self.entities = _parse_dict_file(dict_path)
        self._by_name: Dict[str, EntityInfo] = {
            e.name: e for e in self.entities.values()
        }
        if html_path:
            _parse_html_descriptions(html_path, self.entities)

        # Build section index
        self._sections: Dict[str, List[str]] = {}
        for e in self.entities.values():
            if e.section:
                self._sections.setdefault(e.section, []).append(e.name)

        # Build reverse reference index: entity_name -> [(from_entity, attr_name)]
        self._reverse_refs: Dict[str, List[dict]] = {}
        for e in self.entities.values():
            for attr in e.attributes:
                if attr.is_reference():
                    ref_id = attr.get_reference_entity_id()
                    if ref_id and ref_id in self.entities:
                        target_name = self.entities[ref_id].name
                        self._reverse_refs.setdefault(target_name, []).append({
                            'from_entity': e.name,
                            'attribute': attr.name,
                            'is_list': attr.is_aggregate(),
                        })

        logger.info(f"Schema loaded: {len(self.entities)} entities, {len(self._sections)} sections")

    def get_entity(self, name: str) -> Optional[EntityInfo]:
        return self._by_name.get(name)

    def get_entity_by_id(self, eid: int) -> Optional[EntityInfo]:
        return self.entities.get(eid)

    def get_all_entity_names(self) -> List[str]:
        return sorted(self._by_name.keys())

    def get_sections(self) -> Dict[str, List[str]]:
        """Return {section_name: [entity_names]}."""
        return dict(self._sections)

    def search_entities(self, keyword: str, limit: int = 15) -> List[dict]:
        """Fuzzy search entities by keyword in name, description, section, attributes."""
        keyword_lower = keyword.lower()
        results = []

        for e in self.entities.values():
            score = 0
            # Exact name match
            if keyword_lower == e.name.lower():
                score = 100
            elif keyword_lower in e.name.lower():
                score = 50
            # Description match
            if keyword_lower in e.description.lower():
                score += 30
            # Section match
            if keyword_lower in e.section.lower():
                score += 20
            # Attribute name match
            for attr in e.attributes:
                if keyword_lower in attr.name.lower():
                    score += 10
                    break
                if keyword_lower in attr.description.lower():
                    score += 5
                    break

            if score > 0:
                results.append({
                    'name': e.name,
                    'id': e.id,
                    'description': e.description,
                    'section': e.section,
                    'attribute_count': len(e.attributes),
                    'score': score,
                })

        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]

    def get_entity_schema(self, name: str) -> Optional[dict]:
        """Get full schema for entity including inherited attributes."""
        entity = self._by_name.get(name)
        if not entity:
            return None

        all_attrs = entity.get_all_attributes(self.entities)

        attrs_info = []
        for a in all_attrs:
            info = {
                'name': a.name,
                'datatype': a.datatype,
                'mandatory': a.mandatory,
            }
            if a.description:
                info['description'] = a.description
            if a.is_reference():
                ref_id = a.get_reference_entity_id()
                if ref_id and ref_id in self.entities:
                    info['references'] = self.entities[ref_id].name
            if a.is_aggregate():
                info['is_list'] = True
            attrs_info.append(info)

        result = {
            'name': entity.name,
            'id': entity.id,
            'section': entity.section,
            'attribute_count': len(attrs_info),
            'attributes': attrs_info,
        }
        if entity.description:
            result['description'] = entity.description
        if entity.supertype_id and entity.supertype_id in self.entities:
            result['supertype'] = self.entities[entity.supertype_id].name

        # Subtypes
        subtypes = [e.name for e in self.entities.values() if e.supertype_id == entity.id]
        if subtypes:
            result['subtypes'] = subtypes

        # Reverse references (who references this entity)
        rev_refs = self.get_reverse_references(name)
        if rev_refs:
            result['referenced_by'] = rev_refs

        return result

    def get_entity_description(self, name: str) -> Optional[str]:
        """Get human-readable description of entity in Russian."""
        entity = self._by_name.get(name)
        if not entity:
            return None

        lines = []
        display = entity.description or entity.name
        lines.append(f"Сущность: {entity.name} ({display})")
        if entity.section:
            lines.append(f"Раздел: {entity.section}")
        if entity.supertype_id and entity.supertype_id in self.entities:
            lines.append(f"Базовый тип: {self.entities[entity.supertype_id].name}")

        all_attrs = entity.get_all_attributes(self.entities)
        if all_attrs:
            lines.append(f"\nАтрибуты ({len(all_attrs)}):")
            for a in all_attrs:
                mandatory = "обяз." if a.mandatory else "необяз."
                ref = ""
                if a.is_reference():
                    ref_id = a.get_reference_entity_id()
                    if ref_id and ref_id in self.entities:
                        ref = f" → {self.entities[ref_id].name}"
                desc = f" — {a.description}" if a.description else ""
                lines.append(f"  - {a.name} ({a.datatype}{ref}, {mandatory}){desc}")

        # Reverse references
        rev_refs = self.get_reverse_references(name)
        if rev_refs:
            lines.append(f"\nНа эту сущность ссылаются ({len(rev_refs)}):")
            for rr in rev_refs:
                list_mark = " (список)" if rr['is_list'] else ""
                lines.append(f"  - {rr['from_entity']}.{rr['attribute']}{list_mark}")

        return "\n".join(lines)

    def get_reverse_references(self, name: str) -> List[dict]:
        """Get entities that reference the given entity (incoming links)."""
        return self._reverse_refs.get(name, [])

    def get_categories(self) -> List[dict]:
        """Get entity categories for the system prompt (section-based grouping)."""
        categories = []
        for section, entity_names in sorted(self._sections.items()):
            categories.append({
                'name': section,
                'entities': sorted(entity_names),
                'count': len(entity_names),
            })
        return categories


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_schema_instance: Optional[Schema] = None


def get_schema(dict_path: str = None, html_path: str = None) -> Schema:
    """Get or create Schema singleton."""
    global _schema_instance
    if _schema_instance is None:
        if dict_path is None:
            from ILS_reports_agent.config import Config
            dict_path = Config.DICT_FILE_PATH
            html_path = Config.HTML_SCHEMA_PATH
        _schema_instance = Schema(dict_path, html_path)
    return _schema_instance
