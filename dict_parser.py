"""
Parser for APL PSS A dictionary file.
Extracts entity definitions, attributes, and type information.
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class AttributeInfo:
    """Information about an entity attribute"""
    id: int
    entity_id: int
    name: str
    datatype: str
    mandatory: bool  # F = mandatory, T = optional
    offset: int

    def is_reference(self) -> bool:
        """Check if attribute is a reference to another entity"""
        return self.datatype.startswith('instance of') or self.datatype.startswith('aggregate of')

    def get_reference_type(self) -> Optional[int]:
        """Extract referenced entity ID if this is a reference"""
        if self.is_reference():
            match = re.search(r'(\d+)', self.datatype)
            if match:
                return int(match.group(1))
        return None

    def is_aggregate(self) -> bool:
        """Check if attribute is an aggregate (array/list)"""
        return 'aggregate' in self.datatype.lower()


@dataclass
class EntityInfo:
    """Information about an entity definition"""
    id: int
    name: str
    supertype_id: Optional[int] = None
    attributes: List[AttributeInfo] = field(default_factory=list)

    def get_all_attributes(self, entities_dict: Dict[int, 'EntityInfo']) -> List[AttributeInfo]:
        """Get all attributes including inherited from supertypes"""
        all_attrs = list(self.attributes)

        # Add attributes from supertype chain
        current_supertype_id = self.supertype_id
        while current_supertype_id and current_supertype_id in entities_dict:
            supertype = entities_dict[current_supertype_id]
            all_attrs.extend(supertype.attributes)
            current_supertype_id = supertype.supertype_id

        return all_attrs


class DictParser:
    """Parser for apl_pss_a.dict file"""

    def __init__(self, dict_file_path: str):
        self.dict_file_path = dict_file_path
        self.entities: Dict[int, EntityInfo] = {}
        self.entity_by_name: Dict[str, EntityInfo] = {}

    def parse(self) -> Dict[int, EntityInfo]:
        """Parse the dictionary file and return entity definitions"""
        with open(self.dict_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Parse entity definitions (E prefix)
            if line.startswith('E '):
                self._parse_entity_line(line)

            # Parse attribute definitions (A prefix)
            elif line.startswith('A '):
                self._parse_attribute_line(line)

        return self.entities

    def _parse_entity_line(self, line: str):
        """Parse entity definition line
        Format: E <id> <name> [<supertype_id>|N|Y <supertype_id1> <supertype_id2>]
        Example: E 33 product_category N
        Example: E 35 product_related_product_category 33
        Example: E 139 complex_entity Y 39 38  (complex entity with multiple supertypes)
        """
        parts = line.split()
        if len(parts) < 3:
            return

        entity_id = int(parts[1])
        entity_name = parts[2]

        # Parse supertype (N means no supertype, Y means complex entity)
        supertype_id = None
        if len(parts) > 3:
            if parts[3] == 'N':
                # No supertype
                supertype_id = None
            elif parts[3] == 'Y':
                # Complex entity with multiple supertypes - take first one
                if len(parts) > 4:
                    try:
                        supertype_id = int(parts[4])
                    except ValueError:
                        pass
            else:
                # Simple supertype
                try:
                    supertype_id = int(parts[3])
                except ValueError:
                    pass

        entity = EntityInfo(
            id=entity_id,
            name=entity_name,
            supertype_id=supertype_id
        )

        self.entities[entity_id] = entity
        self.entity_by_name[entity_name] = entity

    def _parse_attribute_line(self, line: str):
        """Parse attribute definition line
        Format: A <id> e <entity_id> <F|T> <offset> <datatype>
        Example: A 123 e 33 F 0 string
        Example: A 456 e 35 T 2 instance of 20
        """
        parts = line.split(maxsplit=6)
        if len(parts) < 7 or parts[2] != 'e':
            return

        attr_id = int(parts[1])
        entity_id = int(parts[3])
        mandatory = parts[4] == 'F'
        offset = int(parts[5])
        raw_datatype = parts[6] if len(parts) > 6 else 'unknown'

        # Extract attribute name (first word) and actual datatype (rest)
        attr_name, datatype = self._extract_attribute_name(raw_datatype, attr_id)

        # Find entity and add attribute
        if entity_id in self.entities:
            attr = AttributeInfo(
                id=attr_id,
                entity_id=entity_id,
                name=attr_name,
                datatype=datatype,
                mandatory=mandatory,
                offset=offset
            )

            self.entities[entity_id].attributes.append(attr)

    KNOWN_TYPE_KEYWORDS = {'string', 'integer', 'real', 'float', 'boolean',
                           'enumeration', 'number', 'instance', 'aggr', 'select',
                           'aggregate', 'list', 'set', 'bag'}

    def _extract_attribute_name(self, raw_datatype: str, attr_id: int) -> tuple:
        """Extract (attribute_name, datatype) from raw datatype string.

        Example: "formation_type enumeration" -> ("formation_type", "enumeration")
        Example: "frame_of_reference aggr instance 23" -> ("frame_of_reference", "aggr instance 23")
        Example: "string" -> ("attr_123", "string")  (no name prefix)
        """
        words = raw_datatype.split()
        if len(words) >= 2 and words[0].lower() not in self.KNOWN_TYPE_KEYWORDS:
            return words[0], ' '.join(words[1:])
        # Fallback: no name prefix, entire string is datatype
        return f"attr_{attr_id}", raw_datatype

    def get_entity_by_name(self, name: str) -> Optional[EntityInfo]:
        """Get entity by name"""
        return self.entity_by_name.get(name)

    def get_entity_by_id(self, entity_id: int) -> Optional[EntityInfo]:
        """Get entity by ID"""
        return self.entities.get(entity_id)

    def get_all_entity_names(self) -> List[str]:
        """Get list of all entity names"""
        return sorted(self.entity_by_name.keys())

    def get_entity_hierarchy(self, entity_id: int) -> List[int]:
        """Get inheritance hierarchy for an entity (from base to current)"""
        hierarchy = []
        current_id = entity_id

        while current_id and current_id in self.entities:
            hierarchy.insert(0, current_id)
            entity = self.entities[current_id]
            current_id = entity.supertype_id

        return hierarchy

    def get_subtypes(self, entity_id: int) -> List[EntityInfo]:
        """Get all direct subtypes of an entity"""
        subtypes = []
        for entity in self.entities.values():
            if entity.supertype_id == entity_id:
                subtypes.append(entity)
        return subtypes

    def get_python_type(self, datatype: str) -> str:
        """Convert APL datatype to Python type hint"""
        datatype_lower = datatype.lower()

        if 'string' in datatype_lower:
            return 'str'
        elif 'integer' in datatype_lower:
            return 'int'
        elif 'real' in datatype_lower or 'float' in datatype_lower:
            return 'float'
        elif 'boolean' in datatype_lower:
            return 'bool'
        elif 'instance of' in datatype_lower:
            return 'dict'  # Reference to another entity
        elif 'aggregate' in datatype_lower:
            return 'list'  # Array/collection
        else:
            return 'Any'

    def export_to_json_schema(self) -> Dict:
        """Export entity definitions as JSON schema"""
        schemas = {}

        for entity in self.entities.values():
            schema = {
                "type": "object",
                "entity_id": entity.id,
                "entity_name": entity.name,
                "supertype_id": entity.supertype_id,
                "properties": {},
                "required": []
            }

            for attr in entity.attributes:
                schema["properties"][attr.name] = {
                    "type": self.get_python_type(attr.datatype),
                    "datatype": attr.datatype,
                    "attr_id": attr.id
                }

                if attr.mandatory:
                    schema["required"].append(attr.name)

                # Add reference information
                if attr.is_reference():
                    ref_type = attr.get_reference_type()
                    if ref_type:
                        schema["properties"][attr.name]["$ref"] = f"#/entities/{ref_type}"

            schemas[entity.id] = schema

        return schemas


# Singleton instance for global access
_parser_instance: Optional[DictParser] = None


def get_dict_parser(dict_file_path: str = None) -> DictParser:
    """Get or create dictionary parser singleton"""
    global _parser_instance

    if _parser_instance is None:
        if dict_file_path is None:
            import os
            # Default path
            dict_file_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'doc',
                'apl_pss_a.dict'
            )

        _parser_instance = DictParser(dict_file_path)
        _parser_instance.parse()

    return _parser_instance
