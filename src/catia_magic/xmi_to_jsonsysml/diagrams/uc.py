
from diagrams.common import extract_element
from utils.getter_utils import (
    find_element_by_id,
    get_attribute_with_ns,
    get_element_stereotypes,
    get_element_owner
)
from utils.common_utils import extract_relationship
from utils.pkg_utils import extract_package
from utils.uc_utils import extract_usecase

def extract_uc(diagram):
    """
    Extracts a SysML Use Case Diagram from the XMI file and converts it to Json-SysML.

    Args:
        diagram (Element): The XML element representing the SysML Use Case Diagram.

    Returns:
        uc (dict): A dictionary representing the SysML Use Case Diagram in Json-SysML format.
    """
    diagram_name = diagram.get("name")
    diagram_id = get_attribute_with_ns("id", diagram)
    parent = diagram.getparent().getparent().getparent()
    diagram_owner = get_element_owner(diagram.get("ownerOfDiagram"), parent)
    
    uc = {
        "diagramType": "uc",
        "name": diagram_name,
        "id": diagram_id,
        "owner": diagram_owner,
        "systemBoundary": {},
        "useCases": []
    }

    used_elements = diagram[0][0][0][0].findall("usedElements")
    used_elements_ids = [el.text.strip() for el in used_elements]
    use_case_owners = {}

    for used_element_id in used_elements_ids:
        element = find_element_by_id(used_element_id, parent)
        if element is None:
            continue
        xmi_type = get_attribute_with_ns("type", element)

        if xmi_type == "uml:UseCase":
            uc["useCases"].append(extract_usecase(element))
            if element.xpath("./subject"):
                for subject in element.xpath("./subject"):
                    owner = find_element_by_id(
                        get_attribute_with_ns("idref", subject),
                        parent
                    )
                    use_case_owners[owner] = use_case_owners.get(owner, 0) + 1
            else:
                use_case_owners[element.getparent()] = use_case_owners.get(element.getparent(), 0) + 1

        elif xmi_type in ["uml:Package", "uml:Model"]:
            package = extract_package(element)
            if "useCaseModel" in package.get("stereotypes", []):
                uc["systemBoundary"] = {
                    "name": package.get("name"),
                    "idref": used_element_id,
                    "stereotypes": package.get("stereotypes")
                }
            else:
                uc.setdefault("packages", []).append(package)

        elif xmi_type == "uml:Association":
            relationship = extract_relationship(element)
            relationship["type"] = relationship["type"].replace("Directed", "")
            uc.setdefault("relationships", []).append(relationship)

        else:
            uc = extract_element(uc, element)

    if uc["systemBoundary"] == {} and use_case_owners != {}:
        system_boundary_elem = max(use_case_owners, key=use_case_owners.get)
        id = get_attribute_with_ns("id", system_boundary_elem)
        if id in used_elements_ids:
            uc["systemBoundary"] = {
                "name": system_boundary_elem.get("name"),
                "idref": id,
                "stereotypes": get_element_stereotypes(system_boundary_elem)
            }

    if uc["systemBoundary"] != {}:
        owned_use_cases = []
        for use_case in uc["useCases"]:
            use_case_elem = find_element_by_id(use_case["id"], parent)
            first_option = get_attribute_with_ns("id", use_case_elem.getparent()) == uc["systemBoundary"]["idref"]
            second_option = (
                use_case_elem.xpath("./subject") and any(
                    get_attribute_with_ns("idref", subject) == uc["systemBoundary"]["idref"]
                    for subject in use_case_elem.xpath("./subject")
                )
            )
            if first_option or second_option:
                owned_use_cases.append(use_case["id"])
        if owned_use_cases:
            uc["systemBoundary"]["ownedUseCases"] = owned_use_cases

        # To avoid duplication, remove system boundary from blocks and packages
        if "blocks" in uc:
            uc["blocks"] = [block for block in uc["blocks"] if block["id"] != uc["systemBoundary"]["idref"]]
        if "packages" in uc:
            uc["packages"] = [package for package in uc["packages"] if package["id"] != uc["systemBoundary"]["idref"]]

    uc = {key: value for key, value in uc.items() if value not in [None, [], ""]}

    return uc