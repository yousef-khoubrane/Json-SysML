
from diagrams.common import extract_element
from utils.getter_utils import (
    find_element_by_id,
    get_attribute_with_ns,
    get_element_owner
)
from utils.stm_utils import (
    extract_vertex,
    extract_transition,
    sort_vertices
)

def extract_stm(diagram):
    """
    Extracts a SysML State Machine Diagram from the XMI file and converts it to Json-SysML.

    Args:
        diagram (Element): The XML element representing the SysML State Machine Diagram.

    Returns:
        stm (dict): A dictionary representing the SysML State Machine Diagram in Json-SysML format.
    """
    diagram_name = diagram.get("name")
    diagram_id = get_attribute_with_ns("id", diagram)
    parent = diagram.getparent().getparent().getparent()
    diagram_owner = get_element_owner(diagram.get("ownerOfDiagram"), parent)
    
    stm = {
        "diagramType": "stm",
        "name": diagram_name,
        "id": diagram_id,
        "owner": diagram_owner,
        "context": {},
        "connectionPoints": [],
        "vertices": [],
        "transitions": [],
    }

    used_elements = diagram[0][0][0][0].findall("usedElements")
    used_elements_ids = [el.text.strip() for el in used_elements]

    if diagram.get("context"):
        context_element = find_element_by_id(diagram.get("context"), parent)
    else:
        context_element = find_element_by_id(diagram.get("ownerOfDiagram"), parent) 
    if context_element is not None:
        stm["context"] = {
            "name": context_element.get("name"),
            "idref": get_attribute_with_ns("id", context_element)
        }

    for used_element_id in used_elements_ids:
        element = find_element_by_id(used_element_id, parent)
        if element is None:
            continue

        if element.tag == "connectionPoint":
            stm["connectionPoints"].append(extract_vertex(element))

        elif element.tag == "subvertex":
            stm["vertices"].append(extract_vertex(element))

        elif element.tag == "transition":
            stm["transitions"].append(extract_transition(element))

        elif element.tag in ["doActivity", "entry", "exit"]:
            continue
        
        else:
            stm = extract_element(stm, element)

    # Nested vertices
    vertex_lookup = {
        v["id"]: v 
        for v in stm.get("vertices", []) + stm.get("connectionPoints", [])
        if "id" in v
    }
    for vertex in stm.get("vertices", [])[:]:
        for idx, cp_id in enumerate(vertex.get("connectionPoints", [])):
            subvertex = vertex_lookup.get(cp_id)
            if subvertex:
                vertex["connectionPoints"][idx] = subvertex
                if subvertex in stm["vertices"]:
                    stm["vertices"].remove(subvertex)
                else:
                    stm["connectionPoints"].remove(subvertex)
        for region_idx, region in enumerate(vertex.get("regions", [])):
            new_region = []
            for id in region:
                subvertex = vertex_lookup.get(id)
                if subvertex:
                    new_region.append(subvertex)
                    if subvertex in stm["vertices"]:
                        stm["vertices"].remove(subvertex)
                    else:
                        stm["connectionPoints"].remove(subvertex)
            vertex["regions"][region_idx] = sort_vertices(new_region)        

    # Reorder the vertices list
    stm["vertices"] = sort_vertices(stm.get("vertices", []))

    stm = {key: value for key, value in stm.items() if value not in [None, [], ""]}

    return stm