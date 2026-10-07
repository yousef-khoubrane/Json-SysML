
from diagrams.common import extract_element
from utils.getter_utils import (
    find_element_by_id,
    get_attribute_with_ns,
    get_element_owner
)
from utils.act_utils import (
    extract_node,
    extract_action,
    extract_edge,
    extract_partition,
    extract_interruptible_region
)

def extract_act(diagram):
    """
    Extracts a SysML Activity Diagram from the XMI file and converts it to Json-SysML.

    Args:
        diagram (Element): The XML element representing the SysML Activity Diagram.

    Returns:
        act (dict): A dictionary representing the SysML Activity Diagram in Json-SysML format.
    """
    diagram_name = diagram.get("name")
    diagram_id = get_attribute_with_ns("id", diagram)
    parent = diagram.getparent().getparent().getparent()
    diagram_owner = get_element_owner(diagram.get("ownerOfDiagram"), parent)
    
    act = {
        "diagramType": "act",
        "name": diagram_name,
        "id": diagram_id,
        "owner": diagram_owner,
        "context": {
            "name": find_element_by_id(
                diagram.get("context"),
                parent,
                {}
            ).get("name", ""),
            "idref": diagram.get("context")
        },
        "nodes": [],
        "actions": [],
        "edges": [],
        "partitions": [],
        "interruptibleRegions": []
    }

    if act["context"]["idref"] == act["owner"]["idPath"].rsplit("::", 1)[-1]:
        del act["context"]

    used_elements = diagram[0][0][0][0].findall("usedElements")
    used_elements_ids = [el.text.strip() for el in used_elements]

    for used_element_id in used_elements_ids:
        element = find_element_by_id(used_element_id, parent)
        if element is None:
            continue
        xmi_type = get_attribute_with_ns("type", element)

        if xmi_type.endswith("Node"):
            act["nodes"].append(extract_node(element))

        elif xmi_type.endswith("Action"):
            act["actions"].append(extract_action(element))

        elif xmi_type.endswith("Flow"):
            act["edges"].append(extract_edge(element))

        elif xmi_type == "uml:ActivityPartition":
            act["partitions"].append(extract_partition(element))

        elif xmi_type == "uml:InterruptibleActivityRegion":
            act["interruptibleRegions"].append(extract_interruptible_region(element))

        else:
            act = extract_element(act, element)

    # Remove references to owned nodes not present on the diagram
    owned_nodes_keys = ["ownedNodesAndActions", "executableNodes"]
    for node in act.get("nodes", []):
        for owned_nodes in owned_nodes_keys:
            if owned_nodes in node:
                node[owned_nodes] = [n for n in node[owned_nodes] if n in used_elements_ids]

    # Reorder the nodes list
    initial_nodes, in_between_nodes, flow_final_nodes, activity_final_nodes = [], [], [], []
    for v in act.get("nodes", []):
        if v.get("type") == "InitialNode":
            initial_nodes.append(v)
        elif v.get("type") == "FlowFinalNode":
            flow_final_nodes.append(v)
        elif v.get("type") == "ActivityFinalNode":
            activity_final_nodes.append(v)
        else:
            in_between_nodes.append(v)
    act["nodes"] = initial_nodes + in_between_nodes + flow_final_nodes + activity_final_nodes

    act = {key: value for key, value in act.items() if value not in [None, [], ""]}

    return act