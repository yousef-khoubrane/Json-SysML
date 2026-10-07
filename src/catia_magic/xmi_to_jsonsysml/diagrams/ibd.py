
from diagrams.common import extract_element
from utils.getter_utils import (
    find_element_by_id,
    get_attribute_with_ns,
    get_element_owner
)
from utils.ibd_utils import (
    extract_property,
    extract_port,
    extract_connector,
    check_if_shortcut_property,
    structure_nested_properties
)

def extract_ibd(diagram):
    """
    Extracts a SysML Internal Block Diagram from the XMI file and converts it to Json-SysML.

    Args:
        diagram (Element): The XML element representing the SysML Internal Block Diagram.

    Returns:
        ibd (dict): A dictionary representing the SysML Internal Block Diagram in Json-SysML format.
    """
    diagram_name = diagram.get("name")
    diagram_id = get_attribute_with_ns("id", diagram)
    parent = diagram.getparent().getparent().getparent()
    diagram_owner = get_element_owner(diagram.get("ownerOfDiagram"), parent)

    ibd = {
        "diagramType": "ibd",
        "name": diagram_name,
        "id": diagram_id,
        "owner": diagram_owner,
        "context": {},
        "properties": [],
        "ports": [],
        "connectors": []
    }

    used_elements = diagram[0][0][0][0].findall("usedElements")
    used_elements_ids = [el.text.strip() for el in used_elements]

    if diagram.get("context"):
        context_element = find_element_by_id(diagram.get("context"), parent)
    else:
        context_element = find_element_by_id(diagram.get("ownerOfDiagram"), parent) 
    if context_element is not None:
        context_block = {
            "name": context_element.get("name"),
            "idref": get_attribute_with_ns("id", context_element)
        }
        ports = []
        for attribute in context_element.findall("ownedAttribute"):
            if get_attribute_with_ns("type", attribute) == "uml:Port":
                port_id = get_attribute_with_ns("id", attribute)
                if port_id in used_elements_ids:
                    ports.append(port_id)
        if ports:
            context_block["ports"] = ports
        ibd["context"] = context_block

    for used_element_id in used_elements_ids:
        element = find_element_by_id(used_element_id, parent)
        if element is None:
            continue
        xmi_type = get_attribute_with_ns("type", element)

        if xmi_type == "uml:Property":
            property = extract_property(
                element,
                include_ports=True,
                diagram_elements_ids=used_elements_ids
            )
            property = check_if_shortcut_property(property, diagram_id, parent)
            ibd["properties"].append(property)

        elif xmi_type == "uml:Port":
            ibd["ports"].append(extract_port(element))

        elif xmi_type == "uml:Connector":
            ibd["connectors"].append(extract_connector(element))

        else:
            ibd = extract_element(ibd, element)

    ibd = structure_nested_properties(ibd, parent.getroottree().getroot())

    ibd = {key: value for key, value in ibd.items() if value not in [None, [], ""]}

    return ibd