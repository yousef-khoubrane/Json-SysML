
from utils.getter_utils import get_boolean_values
from utils.helpers import remove_html_tags, reorder_dict

import copy
import json

def finalize_extraction(element, element_dict):
    """
    Finalizes the extraction of an element by performing the following operations:
    1. If the element has an "ID" attribute that matches the "id" in the element_dict, it replaces "id" with "originalID".
    2. Updates the element_dict with boolean values extracted from the element's attributes.
    3. Removes any empty fields from the element_dict.
    """
    if "id" in element_dict and element.get("ID", "not_found") == element_dict["id"]:
        element_dict["originalID"] = element_dict.pop("id")        

    element_dict.update(get_boolean_values(element))
    element_dict = remove_empty_fields(element_dict)
    return element_dict

def remove_empty_fields(data):
    """
    Recursively removes empty fields from a dictionary or list.
    """
    if isinstance(data, dict):
        cleaned = {
            key: remove_empty_fields(value)
            for key, value in data.items()
        }
        return {k: v for k, v in cleaned.items() if v not in ("", None, [], {})}
    elif isinstance(data, list):
        cleaned_list = [remove_empty_fields(item) for item in data]
        return [item for item in cleaned_list if item not in ("", None, [], {})]
    else:
        return data
    
def sort_diagrams(model):
    """
    Sorts diagrams first by their type (according to a custom order)
    and then alphabetically by name within each type.
    """
    # Define the custom order of diagram types
    type_order = ["bdd", "req", "pkg", "uc", "ibd", "par", "act", "sd", "stm"]
    
    # Create a mapping of type to its index (priority)
    # Default to a high number if the type isn't in our list
    order_map = {t: i for i, t in enumerate(type_order)}

    diagrams = model.get("diagrams", [])

    if diagrams:
        # Sort using a tuple key: (Type Priority, Name)
        diagrams.sort(key=lambda d: (
            order_map.get(d.get("diagramType", ""), 999), 
            d.get("name", "").lower()
        ))
        
        model["diagrams"] = diagrams
        
    return model

def sort_diagram_fields(model):
    """
    Sorts the fields in each diagram of the model.
    """
    first_keys = ["diagramType", "name", "id", "owner"]
    first_diagram_keys = {
        "bdd": ["blocks", "packages", "actors", "interfaces", "signals", "dataTypes",
                "flowSpecifications", "enumerations", "units", "instanceSpecifications"],
        "pkg": ["packages", "blocks", "requirements", "useCases"],
        "req": ["requirements", "blocks", "testCases", "useCases", "packages"],
        "uc": ["systemBoundary", "useCases", "actors", "blocks", "requirements",
               "packages", "testCases"],
    }
    if "diagrams" in model:
        for i, diagram in enumerate(model["diagrams"]):
            if diagram.get("diagramType", "") in first_diagram_keys:
                initial_keys = first_keys + first_diagram_keys[diagram["diagramType"]]
            else:
                initial_keys = None
            model["diagrams"][i] = reorder_dict(
                diagram,
                first_keys=initial_keys,
                last_keys=["referencedDiagrams", "relationships", "comments", "taggedValues"]
            )
    return model
    
def clean_strings(data):
    """
    Recursively cleans string fields in the data structure by stripping whitespace.
    """
    if isinstance(data, dict):
        return {
            key: clean_strings(value)
            for key, value in data.items()
        }
    elif isinstance(data, list):
        return [clean_strings(item) for item in data]
    elif isinstance(data, str):
        return remove_html_tags(data.replace("\n", " "))
    else:
        return data
    
def deduplicate_element_definitions(model):
    """
    Traverses the diagrams in a Json-SysML model and deduplicates shared elements.
    The first occurrence of an element (identified by 'id') is kept intact.
    Subsequent occurrences are reduced to contain only their 'id' and 'name'.
    """
    seen_ids = set()
    diagrams = model.get("diagrams", [])
    
    for diagram in diagrams:
        for field_name, field_value in diagram.items():
            if field_name not in [
                "blocks", "classes", "packages", "interfaces", "signals", "dataTypes", "flowSpecifications",
                "enumerations", "units", "instanceSpecifications", "useCases", "actors", "requirements",
                "testCases", "activities"
            ]:
                continue
            if isinstance(field_value, list):
                for index, child in enumerate(field_value):
                    if isinstance(child, dict) and "id" in child:
                        element_id = child["id"]
                        
                        if element_id in seen_ids:
                            # Replace the full definition with a reference containing only id and name
                            reduced_element = {}
                            if "name" in child:
                                reduced_element["name"] = child["name"]
                            reduced_element["id"] = element_id
                                
                            field_value[index] = reduced_element
                        else:
                            # Register the first occurrence of the element
                            seen_ids.add(element_id)
                            
    return model

def remap_ids(data, export_mapping=False, output_file="output/id_mapping.json"):
    """
    Recursively remaps IDs in the data structure to a human-readable format.

    Args:
        data (dict or list): The data structure containing IDs to be remapped.
        export_mapping (bool): If True, exports the ID mapping to a JSON file.
        output_file (str): The file path to export the ID mapping if export_mapping is True.

    Returns:
        dict or list: The data structure with remapped IDs.
    """
    data = copy.deepcopy(data)
    id_map = {}
    counters = {}

    # -------------------------------
    # Helpers
    # -------------------------------

    def get_cleaned_field_key(field_key):
        if field_key.endswith("ies"):
            return field_key[:-3] + "y"
        elif field_key.endswith("vertices"):
            return field_key.replace("vertices", "vertex")
        elif field_key.endswith("classes"):
            return field_key.replace("classes", "class")
        elif field_key.endswith("s"):
            return field_key[:-1]
        return field_key

    def get_new_id(parent_id, field_key, clean_field_key=True):
        cleaned_field_key = get_cleaned_field_key(field_key) if clean_field_key else field_key
        key = (parent_id, cleaned_field_key)
        counters[key] = counters.get(key, 0) + 1
        return f"{parent_id}_{cleaned_field_key}{counters[key]}"

    # ------------------------------
    # FIRST PASS - process "id" fields
    # ------------------------------
    def process_ids(obj, parent_id=None, field_key=None, parent_is_dict=False):
        if isinstance(obj, dict):
            if "id" in obj and field_key != "taggedValues":
                old_id = obj["id"]
                if old_id in id_map:
                    obj["id"] = id_map[old_id]
                else:
                    if parent_is_dict and field_key:
                        new_id = f"{parent_id}_{field_key}"
                    else:
                        new_id = get_new_id(parent_id or "root", field_key or "item")
                    id_map[old_id] = new_id
                    obj["id"] = new_id

                parent_id = obj["id"]

            if "originalID" in obj:
                id_map[obj["originalID"]] = obj["originalID"]

            for k, v in obj.items():
                process_ids(v, parent_id=parent_id, field_key=k, parent_is_dict=True)

        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, list):
                    inner_parent_id = get_new_id(parent_id or "root", field_key or "item")
                    inner_field_key = "vertices" if field_key == "regions" else "items"
                    process_ids(item, parent_id=inner_parent_id, field_key=inner_field_key, parent_is_dict=False)
                else:
                    process_ids(item, parent_id=parent_id, field_key=field_key, parent_is_dict=False)

    # Process the model and the diagrams first
    if "id" in data:
        old_id = data["id"]
        new_id = "model"
        id_map[old_id] = new_id
        data["id"] = new_id
    if "diagrams" in data:
        diagram_counters = {}
        for diagram in data["diagrams"]:
            dtype = diagram.get("diagramType", "diagram")
            diagram_counters[dtype] = diagram_counters.get(dtype, 0) + 1

            diagram_id = f"{dtype}{diagram_counters[dtype]}"
            id_map[diagram["id"]] = diagram_id
            diagram["id"] = diagram_id

            for k, v in diagram.items():
                process_ids(v, parent_id=diagram_id, field_key=k, parent_is_dict=True)

    # ------------------------------
    # SECOND PASS - remap reference IDs
    # ------------------------------
    def replace_ids(obj, parent_id=None, field_key=None, parent_is_dict=False):

        reference_ids_fields = [
            "idref", "referenceActivityIdref", "portOwnerIdref", "sourceIdref", "targetIdref", "connectorIdref"
        ]
        reference_id_lists_fields = [
            "annotatedElements", "ownedUseCases", "ownedNodesAndActions", "executableNodes", "elements", "ports",
            "coveredLifelines", "interruptingEdges"
        ]
        id_paths_fields = ["idPath"]

        if isinstance(obj, dict):
            # If the dict itself has an id, update parent_id
            if "id" in obj:
                parent_id = obj["id"]

            for k, v in obj.items():
                if "id" in obj:
                    field_key = ""
                    parent_is_dict = True

                # --- Single reference fields ---
                if k in reference_ids_fields:
                    if isinstance(v, str):
                        if v in id_map:
                            obj[k] = id_map[v]
                        else:
                            if parent_is_dict and field_key:
                                new_id = f"{parent_id}_{field_key}_{k}"
                            elif parent_is_dict and not field_key:
                                new_id = f"{parent_id}_{k}"
                            elif field_key and not parent_is_dict:
                                new_id = get_new_id(parent_id or "root", field_key) + f"_{k}"
                            else:
                                new_id = get_new_id(parent_id or "root", k)
                            new_id = new_id.replace("_idref", "").replace("Idref", "").replace("Id", "")
                            id_map[v] = new_id
                            obj[k] = new_id

                # --- List reference fields ---
                if k in reference_id_lists_fields and isinstance(v, list):
                    for i, elem in enumerate(v):
                        if isinstance(elem, str):
                            if elem in id_map:
                                v[i] = id_map[elem]
                            else:
                                new_id = get_new_id(parent_id or "root", k)
                                id_map[elem] = new_id
                                v[i] = new_id

                # Path reference fields
                if k in id_paths_fields and isinstance(v, str):
                    parts = v.split("::")
                    remapped_parts = []
                    for i, part in enumerate(parts):
                        if part in id_map:
                            remapped_parts.append(id_map[part])
                        elif part != "":
                            new_parent_id = remapped_parts[i-1] if i > 0 else "root"
                            fallback_id = get_new_id(new_parent_id or "root", "item")
                            id_map[part] = fallback_id
                            remapped_parts.append(fallback_id)
                        else:
                            remapped_parts.append(part)
                            
                    obj[k] = "::".join(remapped_parts)
                    
                # Recurse
                replace_ids(v, parent_id=parent_id, field_key=k, parent_is_dict=True)

        elif isinstance(obj, list):
            for item in obj:
                replace_ids(item, parent_id=parent_id, field_key=field_key, parent_is_dict=False)

    replace_ids(data, parent_is_dict=True)

    if export_mapping:
        with open(output_file, 'w') as f:
            json.dump(id_map, f, indent=2)

    return data