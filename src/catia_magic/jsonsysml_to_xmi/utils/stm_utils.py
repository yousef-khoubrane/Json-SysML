
from utils.helpers import namespaces, gen_id
from utils.getter_utils import (
    find_element_by_id,
    find_root_model,
    get_attribute_with_ns,
    get_closest_package,
)
from utils.common_utils import (
    create_sub_element,
    create_boolean_values,
    create_stereotypes,
)
from utils.act_utils import create_activity
from utils.bdd_utils import create_class

from lxml import etree

def create_state_machine(state_machine, parent_elem):
    if not state_machine.get("isReentrant"):
        state_machine["isReentrant"] = "false"

    state_machine_elem = create_class(state_machine, parent_elem, xmi_type="uml:StateMachine")

    return state_machine_elem

def create_vertex(vertex, parent_elem, diagram_used_elements=[]):
    if "id" not in vertex:
        vertex["id"] = gen_id()
    vertex_id = vertex["id"]
    vertex_elem = find_element_by_id(vertex_id, parent_elem)
    if vertex_elem is None:
        vertex_elem = create_sub_element(parent_elem, "subvertex", attrib={
            etree.QName(namespaces["xmi"], "type"): "uml:" + vertex.get("type", "State"),
            etree.QName(namespaces["xmi"], "id"): vertex_id,
            "name": vertex.get("name", ""),
            "visibility": "public"
        })

    if vertex.get("pseudostateKind", "initial") != "initial":
        vertex_elem.set("kind", vertex.get("pseudostateKind"))
    if vertex.get("pseudostateKind") in ["entryPoint", "exitPoint"] and parent_elem.tag != "region":
        vertex_elem.tag = "connectionPoint"

    for key in ["entry", "doActivity", "exit"]:
        if key in vertex:
            create_related_behavior(vertex[key], vertex_elem, key)

    if vertex.get("stateInvariant"):
        state_invariant_id = f"{vertex['id']}_state_invariant"
        owned_rule_elem = find_element_by_id(state_invariant_id, vertex_elem)
        if owned_rule_elem is None:
            owned_rule_elem = create_sub_element(vertex_elem, "ownedRule", attrib={
                etree.QName(namespaces["xmi"], "type"): "uml:Constraint",
                etree.QName(namespaces["xmi"], "id"): state_invariant_id
            })
            spec_elem = create_sub_element(owned_rule_elem, "specification", attrib={
                etree.QName(namespaces["xmi"], "type"): "uml:OpaqueExpression",
                etree.QName(namespaces["xmi"], "id"): f"{vertex['id']}_state_invariant_spec"
            })
            state_invariant = vertex["stateInvariant"]
            for key in ["body", "language"]:
                if key in state_invariant:
                    key_elem = create_sub_element(spec_elem, key)
                    key_elem.text = state_invariant[key]
            vertex_elem.set("stateInvariant", state_invariant_id)

    if vertex.get("submachine"):
        submachine_id = vertex["submachine"].get("idref")
        if submachine_id:
            create_state_machine(
                {"id": submachine_id, "name": vertex["submachine"].get("name", "")},
                get_closest_package(parent_elem)
            )
            vertex_elem.set("submachine", submachine_id)

    for i, region in enumerate(vertex.get("regions", [])):
        region_id = f"{vertex_id}_region{i+1}"
        region_elem = create_sub_element(vertex_elem, "region", attrib={
            etree.QName(namespaces["xmi"], "type"): "uml:Region",
            etree.QName(namespaces["xmi"], "id"): region_id,
            "visibility": "public",
        })
        for subvertex in region:
            create_vertex(subvertex, region_elem)
            diagram_used_elements.append({"element": subvertex, "element_class": "State"})        
        diagram_used_elements.append({
            "element": {"id": region_id, "nestedVertices": [v["id"] for v in region]},
            "element_class": "Region"
        })

    for cp in vertex.get("connectionPoints", []):
        create_vertex(cp, vertex_elem)
        diagram_used_elements.append({"element": cp, "element_class": "State"})

    create_boolean_values(vertex, vertex_elem)

    create_stereotypes(
        vertex_id,
        vertex.get("stereotypes", []),
        vertex_elem.getroottree().getroot(),
        tagged_values=vertex.get("taggedValues", {})
    )

    return vertex_elem

def create_transition(transition, parent_elem):
    source_id = transition.get("source", {}).get("idref")
    target_id = transition.get("target", {}).get("idref")
    if not source_id or not target_id:
        return None
    
    source_elem = find_element_by_id(source_id, parent_elem)
    target_elem = find_element_by_id(target_id, parent_elem)
    if source_elem is None or target_elem is None:
        return None

    if "id" not in transition:
        transition["id"] = gen_id()

    transition_elem = find_element_by_id(transition["id"], parent_elem)
    if transition_elem is not None:
        transition_elem.set(etree.QName(namespaces["xmi"], "type"), "uml:Transition")
        transition_elem.tag = "transition"
        old_parent = transition_elem.getparent()
        if old_parent is not parent_elem:
            parent_elem.append(transition_elem)
            if len(old_parent) == 0:
                old_parent.getparent().remove(old_parent)
    else:
        transition_elem = create_sub_element(parent_elem, "transition", attrib={
            etree.QName(namespaces["xmi"], "type"): "uml:Transition",
            etree.QName(namespaces["xmi"], "id"): transition["id"],
            "name": transition.get("name", ""),
        })

    transition_elem.set("name", transition.get("name", ""))
    transition_elem.set("visibility", "public")
    transition_elem.set("source", source_id)
    transition_elem.set("target", target_id)

    if transition.get("type"):
        transition_elem.set(etree.QName(namespaces["xmi"], "type"), "uml:" + transition["type"])

    if "kind" in transition:
        transition_elem.set("kind", transition["kind"])

    if transition.get("triggerEvent"):
        event_elem = create_event(transition["triggerEvent"], get_closest_package(parent_elem.getparent()))
        trigger_elem = transition_elem.find("./trigger")
        if trigger_elem is None:
            trigger_elem = create_sub_element(transition_elem, "trigger", attrib={
                etree.QName(namespaces["xmi"], "type"): "uml:Trigger",
                etree.QName(namespaces["xmi"], "id"): f"{transition['id']}_trigger",
                "visibility": "public",
            })
        trigger_elem.set("event", get_attribute_with_ns("id", event_elem))

    if transition.get("guard"):
        guard_id = f"{transition['id']}_guard"
        owned_rule_elem = find_element_by_id(guard_id, transition_elem)
        if owned_rule_elem is None:
            owned_rule_elem = create_sub_element(transition_elem, "ownedRule", attrib={
                etree.QName(namespaces["xmi"], "type"): "uml:Constraint",
                etree.QName(namespaces["xmi"], "id"): guard_id
            })
            spec_elem = create_sub_element(owned_rule_elem, "specification", attrib={
                etree.QName(namespaces["xmi"], "type"): "uml:OpaqueExpression",
                etree.QName(namespaces["xmi"], "id"): f"{transition['id']}_guard_spec"
            })
            guard = transition["guard"]
            for key in ["body", "language"]:
                if key in guard:
                    key_elem = create_sub_element(spec_elem, key)
                    key_elem.text = guard[key]
            transition_elem.set("guard", guard_id)

    if transition.get("effect"):
        create_related_behavior(transition["effect"], transition_elem, "effect")

    create_boolean_values(transition, transition_elem)

    return transition_elem

def create_event(event, parent_elem):
    if "id" not in event:
        event["id"] = gen_id()
    event_id = event["id"]
    event_elem = find_element_by_id(event_id, parent_elem)

    if event_elem is not None:
        return event_elem
    
    xmi_type = "uml:" + event.get("type", "SignalEvent")
    event_elem = create_sub_element(parent_elem, "packagedElement", attrib={
        etree.QName(namespaces["xmi"], "type"): xmi_type,
        etree.QName(namespaces["xmi"], "id"): event_id,
        "name": event.get("name", ""),
    })

    if "signal" in event:
        if "id" not in event["signal"]:
            event["signal"]["id"] = gen_id()
        create_class(event["signal"], parent_elem, xmi_type="uml:Signal", override_existing=False)
        event_elem.set("signal", event["signal"]["id"])
    
    if "when" in event:
        when_elem = create_sub_element(event_elem, "when", attrib={
            etree.QName(namespaces["xmi"], "type"): "uml:TimeExpression",
            etree.QName(namespaces["xmi"], "id"): f"{event_id}_when"
        })
        when = event["when"]
        expr_elem = create_sub_element(when_elem, "expr", attrib={
            etree.QName(namespaces["xmi"], "type"): "uml:LiteralString",
            etree.QName(namespaces["xmi"], "id"): f"{event_id}_when_expr",
        })
        if isinstance(when, dict):
            expr_elem.set(etree.QName(namespaces["xmi"], "type"), "uml:OpaqueExpression")
            for key in ["body", "language"]:
                if key in when:
                    key_elem = create_sub_element(expr_elem, key)
                    key_elem.text = when[key]
        else:
            expr_elem.set("value", str(when))

    if "changeExpression" in event:
        change_expr_elem = create_sub_element(event_elem, "changeExpression", attrib={
            etree.QName(namespaces["xmi"], "type"): "uml:OpaqueExpression",
            etree.QName(namespaces["xmi"], "id"): f"{event_id}_changeExpr",
        })
        for key in ["body", "language"]:
            if key in event["changeExpression"]:
                key_elem = create_sub_element(change_expr_elem, key)
                key_elem.text = event["changeExpression"][key]

    # TODO: Handle structuralFeature if present in tagged values

    create_boolean_values(event, event_elem)

    create_stereotypes(
        event_id,
        event.get("stereotypes", []),
        event_elem.getroottree().getroot(),
    )

    return event_elem

def create_related_behavior(related_behavior, parent_elem, tag):
    if "id" not in related_behavior:
        related_behavior["id"] = gen_id()

    type = related_behavior.get("type", "OpaqueBehavior")
    if type == "ProtocolStateMachine":
        type = "StateMachine"

    related_behavior_elem = find_element_by_id(related_behavior["id"], parent_elem)
    if related_behavior_elem is not None:
        related_behavior_elem.tag = tag
        related_behavior_elem.set(etree.QName(namespaces["xmi"], "type"), "uml:" + type)
    tag_elem = parent_elem.find(f"./{tag}")
    if tag_elem is not None and tag_elem is not related_behavior_elem:
        parent_elem.remove(tag_elem)

    if type == "Activity":
        related_behavior_elem = create_activity(
            related_behavior,
            parent_elem,
            override_existing=False
        )
        related_behavior_elem.tag = tag

    else:
        related_behavior_elem = create_sub_element(parent_elem, tag, attrib={
            etree.QName(namespaces["xmi"], "type"): "uml:" + type,
            etree.QName(namespaces["xmi"], "id"): related_behavior["id"],
            "name": related_behavior.get("name", "")
        })

    for key in ["body", "language"]:
        if key in related_behavior:
            key_elem = create_sub_element(related_behavior_elem, key)
            key_elem.text = related_behavior[key]
    
    return related_behavior_elem

def get_state_element_class(state):

    if state.get("type") == "FinalState":
        return "PseudoState"
    
    kind = state.get("pseudostateKind")
    if not kind:
        return "State"
    elif kind in ("choice", "junction"):
        return "Decision"
    elif kind in ("fork", "join"):
        return "Bar"
    else:
        return "PseudoState"