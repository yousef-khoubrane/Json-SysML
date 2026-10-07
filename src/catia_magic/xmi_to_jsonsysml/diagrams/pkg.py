
from diagrams.common import extract_element
from utils.getter_utils import (
    find_element_by_id,
    get_attribute_with_ns,
    get_element_owner
)

from utils.helpers import all_ns

def extract_pkg(diagram):
    """
    Extracts a SysML Package Diagram from the XMI file and converts it to Json-SysML.

    Args:
        diagram (Element): The XML element representing the SysML Package Diagram.

    Returns:
        pkg (dict): A dictionary representing the SysML Package Diagram in Json-SysML format.
    """
    diagram_name = diagram.get("name")
    diagram_id = get_attribute_with_ns("id", diagram)
    parent = diagram.getparent().getparent().getparent()
    diagram_owner = get_element_owner(diagram.get("ownerOfDiagram"), parent)
    
    pkg = {
        "diagramType": "pkg",
        "name": diagram_name,
        "id": diagram_id,
        "owner": diagram_owner,
        "packages": []
    }

    used_elements = diagram[0][0][0][0].findall("usedElements")
    used_elements_ids = [el.text.strip() for el in used_elements]

    root = diagram.getroottree().getroot()
    diagram_owned_views = None
    for ns in all_ns:
        md_elements = root.xpath(f"./xmi:Extension/filePart/mdOwnedViews/mdElement[@elementClass='DiagramFrame']/elementID[@xmi:idref='{diagram_id}']", namespaces=ns)
        if md_elements:
            diagram_owned_views = md_elements[0].getparent().getparent()
            if not diagram_owned_views.tag == "mdOwnedViews":
                diagram_owned_views = None
            break

    for used_element_id in used_elements_ids:
        element = find_element_by_id(used_element_id, parent)
        if element is None:
            continue
        # if (get_attribute_with_ns("id", element.getparent()) in used_elements_ids
        #     or element.get("ownerOfDiagram") in used_elements_ids):
        #     if diagram_owned_views is not None:
        #         for ns in all_ns:
        #             corresponding_md_elements = diagram_owned_views.xpath(f".//mdElement/elementID[@xmi:idref='{used_element_id}']", namespaces=ns)
        #             if corresponding_md_elements:
        #                 break
        #         if corresponding_md_elements == []:
        #             # if yes, it means the element is only shown within its parent (this can be altered by show/hide inner elements in the UI), so no need to extract it
        #             continue

        pkg = extract_element(pkg, element)

    pkg = {key: value for key, value in pkg.items() if value not in [None, [], ""]}

    return pkg