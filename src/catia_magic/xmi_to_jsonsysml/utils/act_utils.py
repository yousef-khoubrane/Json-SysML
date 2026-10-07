
from utils.helpers import smart_cast,  all_ns
from utils.getter_utils import (
    get_attribute_with_ns,
    get_element_stereotypes,
    find_element_by_id,
    get_multiplicity,
    get_type,
    get_body_and_language
)
from utils.bdd_utils import extract_parameter
from utils.ibd_utils import (
    extract_item_flow,
    extract_property,
    extract_port
)
from utils.stm_utils import extract_trigger_event
from utils.post_processing import finalize_extraction

def extract_activity(element):
    """
    Extracts a SysML activity from an XMI element.

    Args:
        element (Element): The XML element representing the activity.

    Returns:
        dict: A dictionary containing the activity information.
    """
    id = get_attribute_with_ns("id", element)
    name = element.get("name")
    stereotypes, tagged_values = get_element_stereotypes(element, extract_tagged_values=True)

    activity = {
        "name": name,
        "id": id,
        "stereotypes": stereotypes,
        "taggedValues": tagged_values
    }

    for attribute in element.findall("ownedAttribute"):
        xmi_type = get_attribute_with_ns("type", attribute)
        if xmi_type == "uml:Property":
            activity.setdefault("properties", []).append(extract_property(attribute))
        elif xmi_type == "uml:Port":
            activity.setdefault("ports", []).append(extract_port(attribute))
    
    for parameter in element.findall("ownedParameter"):
        activity.setdefault("parameters", []).append(extract_parameter(parameter))

    activity = finalize_extraction(element, activity)
    return activity

def extract_node(element):
    """
    Extracts a SysML activity diagram node from an XMI element.

    Args:
        element (Element): The XML element representing the node.

    Returns:
        dict: A dictionary containing the node information.
    """
    id = get_attribute_with_ns("id", element)
    name = element.get("name")
    stereotypes = get_element_stereotypes(element)
    xmi_type = get_attribute_with_ns("type", element)
    node_type = xmi_type.split(":")[-1]

    node = {
        "name": name,
        "id": id,
        "nodeType": node_type,
        "stereotypes": stereotypes
    }

    type = get_type(element)
    if type:
        node["type"] = type

    if element.get("parameter"):
        param_element = find_element_by_id(
            element.get("parameter"),
            element.getparent()
        )
        if param_element is not None:
            node["parameter"] = {
                "name": param_element.get("name"),
                "idref": element.get("parameter")
            }
            param_type = get_type(param_element)
            if param_type:
                node["parameter"]["type"] = param_type
            if param_element.get("direction"):
                node["parameter"]["direction"] = param_element.get("direction")

    if xmi_type == "uml:ConditionalNode":
        clauses = []
        if element.xpath("./clause"):
            for item in element.xpath("./clause"):
                clause = {
                    "name": item.get("name"),
                    "id": get_attribute_with_ns("id", item),
                    "decider": {
                        "name": find_element_by_id(
                            item.get("decider"),
                            element.getparent(),
                            fallback={}
                        ).get("name"),
                        "idref": item.get("decider")
                    },
                }
                children = ["body", "bodyOutput", "predecessorClause", "successorClause", "test"]
                clause.update(extract_referenced_children(item, children))
                clauses.append(clause)
        node["clauses"] = clauses
    elif xmi_type == "uml:LoopNode":
        node.update(extract_referenced_children(
            element,
            ["bodyOutput", "bodyPart", "setupPart", "test"]
        ))

    if element.xpath("./variable"):
        for var in element.xpath("./variable"):
            variable = {
                "name": var.get("name"),
                "id": get_attribute_with_ns("id", var)
            }
            var_type = get_type(var)
            var_multiplicity = get_multiplicity(var) 
            if var_type:
                variable["type"] = var_type
            if var_multiplicity:
                variable["multiplicity"] = var_multiplicity
            node.setdefault("variables", []).append(variable)

    if element.xpath("./node"):
        node.setdefault("ownedNodesAndActions", []).extend(
            [
                get_attribute_with_ns("id", owned_node)
                for owned_node in element.xpath("./node")
            ]            
        )
    
    if element.xpath("./executableNode"):
        node.setdefault("executableNodes", []).extend(
            [
                get_attribute_with_ns("id", owned_node)
                for owned_node in element.xpath("./executableNode")
            ]            
        )

    input_pins, output_pins = get_pins(element)
    if input_pins:
        node["inputPins"] = input_pins
    if output_pins:
        node["outputPins"] = output_pins

    node = finalize_extraction(element, node)
    return node

def extract_action(element):
    """
    Extracts a SysML action from an XMI element.

    Args:
        element (Element): The XML element representing the action.

    Returns:
        dict: A dictionary containing the action information.
    """
    id = get_attribute_with_ns("id", element)
    name = element.get("name")
    stereotypes, tagged_values = get_element_stereotypes(element, extract_tagged_values=True)
    xmi_type = get_attribute_with_ns("type", element)
    action_type = xmi_type.split(":")[-1]

    action = {
        "name": name,
        "id": id,
        "type": action_type,
        "stereotypes": stereotypes,
        "taggedValues": tagged_values
    }

    elements_of_usage = ["structuralFeature", "signal", "classifier", "operation"]
    for attr in elements_of_usage:
        if element.get(attr):
            action[attr] = {
                "name": find_element_by_id(
                    element.get(attr),
                    element.getparent()
                ).get("name"),
                "id": element.get(attr)
            }
    if element.get("behavior"):
        action["behavior"] = extract_activity(
            find_element_by_id(
                element.get("behavior"),
                element.getparent()
            )
        )

    if element.xpath("./body"):
        action["expression"] = get_body_and_language(element)

    if element.xpath("./value"):
        value = None
        try:
            value = element.find("value").get("value")
            value = smart_cast(value)
        except (TypeError, IndexError, AttributeError):
            pass
        if value != None:
            action["value"] = value

    if element.xpath("./trigger"):
        event = extract_trigger_event(element)
        if event:
            action["triggerEvent"] = event

    input_pins, output_pins = get_pins(element)
    if input_pins:
        action["inputPins"] = input_pins
    if output_pins:
        action["outputPins"] = output_pins

    action = finalize_extraction(element, action)
    return action

def extract_edge(element):
    """
    Extracts a SysML activity diagram edge from an XMI element.

    Args:
        element (Element): The XML element representing the edge.

    Returns:
        dict: A dictionary containing the edge information.
    """
    id = get_attribute_with_ns("id", element)
    xmi_type = get_attribute_with_ns("type", element)
    edge_type = xmi_type.split(":")[-1]
    stereotypes = get_element_stereotypes(element)

    edge = {
        "name": element.get("name"),
        "id": id,
        "type": edge_type,
        "source": {
            "name": find_element_by_id(
                element.get("source"),
                element.getparent()
            ).get("name"),
            "idref": element.get("source")
        },
        "target": {
            "name": find_element_by_id(
                element.get("target"),
                element.getparent()
            ).get("name"),
            "idref": element.get("target")
        },
        "stereotypes": stereotypes
    }

    if element.xpath("./weight"):
        weight = smart_cast(element.xpath("./weight")[0].get("value"))
        if weight != 1: # 1 is the default weight
            edge["weight"] = weight

    if element.xpath("./guard"):
        guard = element.xpath("./guard")[0]
        if guard.get("value"):
            edge["guard"] = guard.get("value")
        elif get_attribute_with_ns("type", guard) == "uml:OpaqueExpression":
            edge["guard"] = get_body_and_language(guard)

    # Include item flows if they exist
    item_flows = []
    for ns in all_ns:
        item_flow_elements = element.getroottree().getroot().xpath(
            f"./packagedElement[@xmi:type='uml:InformationFlow'][realizingActivityEdge/@xmi:idref='{id}']",
            namespaces=ns
        )
        if item_flow_elements:
            for item_flow_element in item_flow_elements:
                item_flows.append(extract_item_flow(item_flow_element))
            break
    if item_flows:
        edge["itemFlows"] = item_flows

    edge = finalize_extraction(element, edge)
    return edge

def extract_partition(element):
    """
    Extracts a SysML activity diagram partition from an XMI element.

    Args:
        element (Element): The XML element representing the partition.

    Returns:
        dict: A dictionary containing the partition information.
    """
    id = get_attribute_with_ns("id", element)
    name = element.get("name")
    stereotypes = get_element_stereotypes(element)
    partition = {
        "name": name,
        "id": id,
        "stereotypes": stereotypes
    }

    if element.get("represents"):
        represented_elem = find_element_by_id(
            element.get("represents"),
            element.getparent(), {}
        )
        represented = {
            "name": represented_elem.get("name"),
            "idref": element.get("represents")
        }
        if represented_elem.get("type"):
            represented["type"] = {
                "name": find_element_by_id(
                    represented_elem.get("type"),
                    element.getparent(),
                    {}
                ).get("name", ""),
                "idref": represented_elem.get("type")
            }
        partition["representedElement"] = represented

    elements = []
    for child in element:
        elements.append(get_attribute_with_ns("idref", child))
    partition["elements"] = elements

    partition = finalize_extraction(element, partition)
    return partition

def extract_interruptible_region(element):
    """
    Extracts a SysML activity diagram interruptible activity region from an XMI element.

    Args:
        element (Element): The XML element representing the interruptible region.

    Returns:
        dict: A dictionary containing the interruptible region information.
    """
    id = get_attribute_with_ns("id", element)
    name = element.get("name")
    stereotypes = get_element_stereotypes(element)
    interruptible_region = {
        "name": name,
        "id": id,
        "stereotypes": stereotypes,
        "elements": [],
        "interruptingEdges": []
    }

    for child in element:
        child_id = get_attribute_with_ns("idref", child)
        if child_id:
            if child.tag == "interruptingEdge":
                interruptible_region["interruptingEdges"].append(child_id)
            else:
                interruptible_region["elements"].append(child_id)

    interruptible_region = finalize_extraction(element, interruptible_region)
    return interruptible_region

def get_pins(element):
    """
    Extracts input and output pins from a SysML activity diagram element.
    """
    input_pins = []
    output_pins = []
    pins = {
        "uml:InputPin": input_pins,
        "uml:OutputPin": output_pins,
        "uml:ValuePin": input_pins,
        "uml:ActionInputPin": input_pins
    }
    for child in element:
        child_type = get_attribute_with_ns("type", child)
        if child_type in pins:
            type = get_type(child)
            pin = {
                "name": child.get("name"),
                "id": get_attribute_with_ns("id", child),
                "pinKind": child_type.split(":")[-1] if child_type.split(":")[-1] not in ["InputPin", "OutputPin"] else "",
                "type": type,
                "ordering": child.get("ordering"), # None means FIFO. Other values are explicit.
            }
            model_ext = child.xpath("./*/modelExtension")
            if model_ext:
                pin["syncElement"] = {"idref": model_ext[0].get("syncElement")}
            multiplicity = get_multiplicity(child)
            if multiplicity:
                pin["multiplicity"] = multiplicity
            pin = finalize_extraction(child, pin)
            pins[child_type].append({key: value for key, value in pin.items() if value != None})
    return input_pins, output_pins

def extract_referenced_children(element, children):
    """"Extracts referenced children from element based on a list of their tag names."""
    references = {}
    for child in children:
        if element.xpath(f"./{child}"):
            child_id = get_attribute_with_ns("idref", element.xpath(f"./{child}")[0])
            references[child] = {
                "name": find_element_by_id(
                    child_id,
                    element.getparent(),
                    fallback={}
                ).get("name"),
                "idref": child_id
            }
    return references
