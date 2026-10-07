
from diagrams.common import extract_element
from utils.helpers import all_ns, is_inside
from utils.getter_utils import (
    find_element_by_id,
    get_attribute_with_ns,
    get_element_owner,
)
from utils.common_utils import extract_geometry_info
from utils.sd_utils import (
    extract_lifeline,
    extract_message,
    extract_fragment,
    extract_constraint
)

import copy

def extract_sd(diagram):
    """
    Extracts a SysML Sequence Diagram from the XMI file and converts it to Json-SysML.

    Args:
        diagram (Element): The XML element representing the SysML Sequence Diagram.

    Returns:
        sd (dict): A dictionary representing the SysML Sequence Diagram in Json-SysML format.
    """
    diagram_name = diagram.get("name")
    diagram_id = get_attribute_with_ns("id", diagram)
    parent = diagram.getparent().getparent().getparent()
    diagram_owner = get_element_owner(diagram.get("ownerOfDiagram"), parent)
    
    sd = {
        "diagramType": "sd",
        "name": diagram_name,
        "id": diagram_id,
        "owner": diagram_owner,
        "context": {},
        "lifelines": [],
        "messages": [],
        "fragments": [],
        "constraints": []
    }

    used_elements = diagram[0][0][0][0].findall("usedElements")
    used_elements_ids = [el.text.strip() for el in used_elements]

    context_element = find_element_by_id(diagram.get("context"), parent)
    context = {
        "name": context_element.get("name"),
        "idref": get_attribute_with_ns("id", context_element),
        "type": get_attribute_with_ns("type", context_element).split(":")[-1]
    } if context_element is not None else {}
    sd["context"] = context
    nested_fragments = {}

    for used_element_id in used_elements_ids:
        element = find_element_by_id(used_element_id, parent)
        if element is None:
            continue
        xmi_type = get_attribute_with_ns("type", element)

        if xmi_type == "uml:Lifeline":
            sd["lifelines"].append(extract_lifeline(element))

        elif xmi_type == "uml:Message":
            sd["messages"].append(extract_message(element))

        elif element.tag == "fragment":
            sd["fragments"].append(extract_fragment(element))
            # Nested structures
            parent_id = get_attribute_with_ns("id", element.getparent())
            if parent_id:
                nested_fragments.setdefault(parent_id, []).append(used_element_id)

        elif xmi_type in ["uml:DurationConstraint", "uml:TimeConstraint"]:
            sd["constraints"].append(extract_constraint(element))

        else:
            sd = extract_element(sd, element)

    # Geometry information extraction
    sd_binary_object = diagram[0][0][0][0].find("binaryObject")
    binary_object_ID = sd_binary_object.get("streamContentID") if sd_binary_object is not None else None
    binary_object = None
    if binary_object_ID:
        for ns in all_ns:
            fileparts = diagram.getroottree().getroot().xpath(f"./xmi:Extension/filePart[@name='{binary_object_ID}']", namespaces=ns)
            if fileparts:
                binary_object = fileparts[0]
                break

    if binary_object is not None:
        try:
            sd_copy = copy.deepcopy(sd)
            for message in sd_copy.get("messages", []):
                for ns in all_ns:
                    md_elements = binary_object.xpath(
                        f".//elementID[@xmi:idref='{message['id']}']",
                        namespaces=ns
                    )
                    if md_elements:
                        message.update(extract_geometry_info(md_elements[0].getparent()))
                    break
            if all("A_Coordinates" in msg for msg in sd_copy.get("messages", [])):
                sd_copy["messages"] = sorted(sd_copy.get("messages", []), key=lambda msg: msg.get("A_Coordinates")[1])
                sd_copy["messages"] = [msg.update({"sequenceNumber": i + 1}) or msg for i, msg in enumerate(sd_copy.get("messages", []))]
            sd = sd_copy
        except (StopIteration, IndexError, AttributeError):
            pass

    try:
        sd_copy = copy.deepcopy(sd)
        for fragment in sd_copy.get("fragments", []):
            for operand in fragment.get("operands", []):
                for ns in all_ns:
                    md_elements = binary_object.xpath(f".//elementID[@xmi:idref='{operand['id']}']", namespaces=ns)
                    if md_elements:
                        operand.update(extract_geometry_info(md_elements[0].getparent()))
                    break
                if "A_Coordinates" in operand:
                    for message in sd_copy.get("messages", []):
                        if is_inside(message, operand):
                            operand.setdefault("nestedMessages", []).append(message["id"])
                    operand.pop("A_Coordinates", None)
                    operand.pop("B_Coordinates", None)
        sd = sd_copy
    except (StopIteration, IndexError, AttributeError):
        pass

    for message in sd.get("messages", []):
        message.pop("A_Coordinates", None)
        message.pop("B_Coordinates", None)

    try:
        sd_copy = copy.deepcopy(sd)
        for lifeline in sd_copy.get("lifelines", []):
            for ns in all_ns:
                md_elements = binary_object.xpath(
                    f".//mdElement[@elementClass='LifeLineLine']//elementID[@xmi:idref='{lifeline['id']}']",
                    namespaces=ns
                )
                if md_elements:
                    lifeline.update(extract_geometry_info(md_elements[0].getparent()))
                break
        if all("A_Coordinates" in lifeline for lifeline in sd_copy.get("lifelines", [])):
            sd_copy["lifelines"] = sorted(sd_copy.get("lifelines", []), key=lambda ll: ll.get("A_Coordinates")[0])
        for lifeline in sd_copy.get("lifelines", []):
            lifeline.pop("A_Coordinates", None)
            lifeline.pop("B_Coordinates", None)
        sd = sd_copy
    except (StopIteration, IndexError, AttributeError):
        pass

    # Nested structures handling for fragments
    fragment_lookup = {f["id"]: f for f in sd.get("fragments", []) if "id" in f}
    for fragment in sd.get("fragments", [])[:]:
        for operand in fragment.get("operands", []):
            nested_messages_to_remove = []
            operand_id = operand.get("id")
            if not operand_id:
                continue
            for child_id in nested_fragments.get(operand_id, []):
                child = fragment_lookup.get(child_id)
                if child:
                    nested_messages_to_remove.extend(
                        [
                            msg_id 
                            for operand in child.get("operands", [])
                            for msg_id in operand.get("nestedMessages", [])
                        ]
                    )
                    # move child under operand
                    operand.setdefault("nestedFragments", []).append(child)
                    sd["fragments"].remove(child)
            # remove duplicate nested messages from parent that already exist in child fragments
            operand["nestedMessages"] = [
                msg_id for msg_id in operand.get("nestedMessages", [])
                if msg_id not in nested_messages_to_remove
            ]

    sd = {key: value for key, value in sd.items() if value not in [None, [], ""]}

    return sd