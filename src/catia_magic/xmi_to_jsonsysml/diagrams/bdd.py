
from diagrams.common import extract_element
from utils.getter_utils import (
    find_element_by_id,
    get_attribute_with_ns,
    get_element_owner
)

def extract_bdd(diagram):
    """
    Extracts a SysML Block Definition Diagram from the XMI file and converts it to Json-SysML.

    Args:
        diagram (Element): The XML element representing the SysML Block Definition Diagram.

    Returns:
        bdd (dict): A dictionary representing the SysML Block Definition Diagram in Json-SysML format.
    """
    diagram_name = diagram.get("name")
    diagram_id = get_attribute_with_ns("id", diagram)
    parent = diagram.getparent().getparent().getparent()
    diagram_owner = get_element_owner(diagram.get("ownerOfDiagram"), parent)
    
    bdd = {
        "diagramType": "bdd",
        "name": diagram_name,
        "id": diagram_id,
        "owner": diagram_owner
    }

    used_elements = diagram[0][0][0][0].findall("usedElements")
    used_elements_ids = [el.text.strip() for el in used_elements]

    for used_element_id in used_elements_ids:

        element = find_element_by_id(used_element_id, parent)
        if element == None:
            continue
        
        bdd = extract_element(bdd, element)
    
    bdd = {key: value for key, value in bdd.items() if value not in [None, [], ""]}

    return bdd