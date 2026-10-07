
from utils.helpers import all_ns
from utils.getter_utils import (
    find_element_by_id,
    get_attribute_with_ns,
    get_element_stereotypes,
    get_body_and_language
)
from utils.bdd_utils import extract_block, extract_parameter
from utils.post_processing import finalize_extraction

def extract_state_machine(element):
    """
    Extracts a SysML state machine from an XMI element.

    Args:
        element (Element): The XML element representing the state machine.

    Returns:
        dict: A dictionary containing the state machine information.
    """
    state_machine = extract_block(element)

    params = []
    for param in element.findall("ownedParameter"):
        params.append(extract_parameter(param))
    if params:
        state_machine["parameters"] = params

    return state_machine

def extract_vertex(element):
    """
    Extracts a SysML state machine diagram vertex (state, pseudostate, etc.) from an XMI element.

    Args:
        element (Element): The XML element representing the vertex.

    Returns:
        dict: A dictionary containing the vertex information.
    """
    id = get_attribute_with_ns("id", element)
    name = element.get("name")
    stereotypes = get_element_stereotypes(element)
    xmi_type = get_attribute_with_ns("type", element)

    vertex = {
        "name": name,
        "id": id,
        "type": xmi_type.split(":")[-1],
        "stereotypes": stereotypes
    }

    related_behaviors = ["entry", "doActivity", "exit"]
    for behavior in related_behaviors:
        if element.xpath(f"./{behavior}"):
            related_behavior = extract_related_behavior(element, behavior)
            if related_behavior:
                vertex[behavior] = related_behavior

    if element.get("stateInvariant"):
        state_invariant_element = find_element_by_id(
            element.get("stateInvariant"),
            element.getparent()
        )
        if state_invariant_element is not None:
            spec = get_body_and_language(state_invariant_element, "specification")
            if spec:
                vertex["stateInvariant"] = spec
    
    if element.get("submachine"):
        vertex["submachine"] = {
            "name": find_element_by_id(
                element.get("submachine"),
                element.getparent(),
                fallback={}
            ).get("name"),
            "idref": element.get("submachine")
        }

    if vertex["type"] == "Pseudostate":
        vertex["pseudostateKind"] = element.get("kind", "initial")

    for cp in element.findall("connectionPoint"):
        vertex.setdefault("connectionPoints", []).append(
            get_attribute_with_ns("id", cp)
        )
        
    for region in element.findall("region"):
        nested_vertices = [
            get_attribute_with_ns("id", v)
            for v in region.findall("subvertex") + region.findall("connectionPoint")
        ]
        vertex.setdefault("regions", []).append(nested_vertices)

    vertex = finalize_extraction(element, vertex)
    return vertex

def extract_transition(element):
    """
    Extracts a SysML state machine diagram transition from an XMI element.

    Args:
        element (Element): The XML element representing the transition.

    Returns:
        dict: A dictionary containing the transition information.
    """
    id = get_attribute_with_ns("id", element)
    name = element.get("name")
    xmi_type = get_attribute_with_ns("type", element)

    transition = {
        "name": name,
        "id": id,
    }

    if element.get("kind"):
        transition["kind"] = element.get("kind")

    for key in ["source", "target"]:
        if element.get(key):
            key_element = find_element_by_id(
                element.get(key),
                element.getparent(),
                fallback={}
            )
            key_name = key_element.get("name", "")
            if key_name == "" and get_attribute_with_ns("type", key_element) == "uml:Pseudostate":
                key_name = key_element.get("kind", "initial") + " pseudostate"
            elif key_name == "" and get_attribute_with_ns("type", key_element) == "uml:FinalState":
                key_name = "final state"
            transition[key] = {
                "name": key_name,
                "idref": element.get(key)
            }

    if element.xpath("./trigger"):
        event = extract_trigger_event(element)
        if event:
            transition["triggerEvent"] = event

    if element.xpath(f"./effect"):
        related_behavior = extract_related_behavior(element, "effect")
        if related_behavior:
            transition["effect"] = related_behavior

    if element.get("guard"):
        owned_rule = find_element_by_id(element.get("guard"), element)
        if owned_rule is not None:
            spec = get_body_and_language(owned_rule, "specification")
            if spec:
                transition["guard"] = spec

    if xmi_type and xmi_type.split(":")[-1] != "Transition":
        transition["type"] = xmi_type.split(":")[-1]

    transition = finalize_extraction(element, transition)
    return transition

def extract_trigger_event(element):
    """
    Extracts a SysML trigger event from the XMI element of its parent.

    Args:
        element (Element): The XML element representing the parent of the trigger.

    Returns:
        dict: A dictionary containing the trigger event information.
    """
    event = {}
    if not element.xpath("./trigger"):
        return event
    event_id = element.xpath("./trigger")[0].get("event")
    if event_id:
        event_element = find_element_by_id(
            event_id,
            element.getparent(),
            {}
        )
        xmi_type = get_attribute_with_ns("type", event_element)
        event_type = xmi_type.split(":")[-1]
        event = {
            "id": event_id,
            "name": event_element.get("name"),
            "type": event_type
        }
        stereotypes, tagged_values = get_element_stereotypes(event_element, extract_tagged_values=True)
        if stereotypes:
            event["stereotypes"] = stereotypes
        if tagged_values != {} and tagged_values.get("structuralFeature"):
            event["structuralFeature"] = tagged_values["structuralFeature"]
        if event_element.xpath("./changeExpression"):
            change_expr = get_body_and_language(event_element, "changeExpression")
            if change_expr:
                event["changeExpression"] = change_expr
        if event_element.get("signal"):
            event["signal"] = extract_block(
                find_element_by_id(
                    event_element.get("signal"),
                    element.getparent(),
                    {}
                )
            )
        if event_element.xpath("./when"):
            when = event_element.xpath("./when")[0]
            if when.xpath("./expr"):
                if when.xpath("./expr")[0].get("value"):
                    expr = when.xpath("./expr")[0].get("value")
                    event["when"] = expr
                elif when.xpath("./expr")[0].xpath("./body"):
                    when_expr = get_body_and_language(when.xpath("./expr")[0])
                    event["when"] = when_expr
        event = finalize_extraction(event_element, event)
    return event

def extract_related_behavior(element, behavior):
    """
    Extracts a related behavior from the XMI element of its parent.

    Args:
        element (Element): The XML element representing the parent of the behavior.
        behavior (str): the tag name of the related behavior.

    Returns:
        dict: A dictionary containing the related behavior information.
    """
    result = {}
    if element.xpath(f"./{behavior}"):
        behavior_element = element.xpath(f"./{behavior}")[0]
        behavior_type = get_attribute_with_ns("type", behavior_element)
        result = {
            "name": behavior_element.get("name", ""),
            "id": get_attribute_with_ns("id", behavior_element),
            "type": behavior_type.split(":")[-1]
        }
        if behavior_type == "uml:Activity":
            call_behavior_actions = []
            for ns in all_ns:
                call_behavior_actions = behavior_element.xpath("./node[@xmi:type='uml:CallBehaviorAction']", namespaces=ns)
                if call_behavior_actions:
                    break
            if call_behavior_actions:
                if len(call_behavior_actions) == 1:
                    ref_act_id = call_behavior_actions[0].get("behavior")
                    if ref_act_id:
                        result["referenceActivityIdref"] = ref_act_id
        elif behavior_type in ["uml:FunctionBehavior", "uml:OpaqueBehavior"]:
            result.update(get_body_and_language(behavior_element))
    return result

def sort_vertices(vertices_list):
    """
    Sorts a list of vertices by putting the initial states at the start and the final states at the end.
    """
    initial_states, in_between_states, final_states = [], [], []
    for v in vertices_list:
        if v.get("pseudostateKind") == "initial":
            initial_states.append(v)
        elif v.get("type") == "FinalState":
            final_states.append(v)
        else:
            in_between_states.append(v)
    return initial_states + in_between_states + final_states