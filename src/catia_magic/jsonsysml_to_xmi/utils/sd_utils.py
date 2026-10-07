
from utils.helpers import namespaces, gen_id, smart_uncast
from utils.getter_utils import (
    find_element_by_id,
    get_attribute_with_ns,
    get_closest_package,
    get_xmi_type_of_value,
    find_root_model
)
from utils.common_utils import (
    create_sub_element,
    create_boolean_values,
    create_stereotypes,
)
from utils.act_utils import create_activity
from utils.bdd_utils import create_operation, create_property

from lxml import etree


def create_lifeline(lifeline, parent_elem):
    if "id" not in lifeline:
        lifeline["id"] = gen_id()
    lifeline_id = lifeline["id"]

    lifeline_elem = find_element_by_id(lifeline_id, parent_elem)
    if lifeline_elem is None:
        lifeline_elem = create_sub_element(parent_elem, "lifeline", attrib={
            etree.QName(namespaces["xmi"], "type"): "uml:Lifeline",
            etree.QName(namespaces["xmi"], "id"): lifeline_id,
            "name": lifeline.get("name", ""),
            "visibility": "public"
        })

    represents_id = lifeline.get("represents", {}).get("idref")
    if represents_id:
        represented_element = find_element_by_id(represents_id, parent_elem)
        if represented_element is None:
            property_elem = create_property({"id": represents_id, **lifeline.get("represents", {})}, parent_elem)
            property_elem.set("visibility", "private")
        lifeline_elem.set("represents", represents_id)

    create_boolean_values(lifeline, lifeline_elem)

    return lifeline_elem

def create_message(message, parent_elem):
    if "id" not in message:
        message["id"] = gen_id()
    message_id = message["id"]

    message_elem = find_element_by_id(message_id, parent_elem)
    if message_elem is not None:
        return message_elem
    
    message_elem = create_sub_element(parent_elem, "message", attrib={
        etree.QName(namespaces["xmi"], "type"): "uml:Message",
        etree.QName(namespaces["xmi"], "id"): message_id,
        "name": message.get("name", ""),
        "visibility": "public"
    })

    if message.get("messageSort"):
        message_elem.set("messageSort", message["messageSort"])

    signature_id = message.get("signature", {}).get("idref")
    if signature_id:
        signature_element = find_element_by_id(signature_id, parent_elem)
        if signature_element is None:
            create_operation({"id": signature_id, "name": message.get("signature", {}).get("name", "")}, parent_elem)
        arg_elem = create_sub_element(message_elem, "argument", attrib={
            etree.QName(namespaces["xmi"], "type"): "uml:LiteralReal",
            etree.QName(namespaces["xmi"], "id"): f"{signature_id}_argument",
        })
        xmi_extension_elem = create_sub_element(
            arg_elem,
            etree.QName(namespaces["xmi"], "Extension"),
            attrib={"extender": "MagicDraw UML 2024x"}
        )
        create_sub_element(xmi_extension_elem, "modelExtension", attrib={
            "syncElement": signature_id
        })
        message_elem.set("signature", signature_id)

    for i, arg in enumerate(message.get("arguments", [])):
        if "id" not in arg:
            arg["id"] = message_id + f"_argument{i+1}"
        arg_elem = create_sub_element(message_elem, "argument", attrib={
            etree.QName(namespaces["xmi"], "type"): "uml:OpaqueExpression",
            etree.QName(namespaces["xmi"], "id"): arg["id"],
            "name": arg.get("name", "")
        })

        if "value" in arg:
            if isinstance(arg["value"], dict):
                for key in ("language", "body"):
                    if key in arg["value"]:
                        key_elem = create_sub_element(arg_elem, key)
                        key_elem.text = arg["value"][key]
            else:
                arg_elem.set(etree.QName(namespaces["xmi"], "type"), get_xmi_type_of_value(None, arg["value"]))
                arg_elem.set("value", smart_uncast(arg["value"]))

    for key, xmi_key in [("source", "sendEvent"), ("target", "receiveEvent")]:
        end_id = message.get(key, {}).get("idref")
        gate_owner = message.get(key, {}).get("gateOwner")
        if end_id:
            end_element = find_element_by_id(end_id, parent_elem)
            if end_element is None:
                end_element = create_lifeline({"id": end_id, "name": message.get(key, {}).get("name", "")}, parent_elem)
            
            fragment_id = f"{message_id}_{key}"
            fragment_elem = find_element_by_id(fragment_id, parent_elem)
            if fragment_elem is None:
                fragment_elem = create_sub_element(parent_elem, "fragment", attrib={
                    etree.QName(namespaces["xmi"], "type"): "uml:MessageOccurrenceSpecification",
                    etree.QName(namespaces["xmi"], "id"): fragment_id,
                    "visibility": "public",
                    "message": message_id
                })
                create_sub_element(fragment_elem, "covered", attrib={
                    etree.QName(namespaces["xmi"], "idref"): end_id
                })

            covered_bys = end_element.findall("coveredBy")
            found = False
            for covered_by in covered_bys:
                if get_attribute_with_ns("idref", covered_by) == fragment_id:
                    found = True
                    break
            if not found:
                create_sub_element(end_element, "coveredBy", attrib={
                    etree.QName(namespaces["xmi"], "idref"): fragment_id
                })
            
            message_elem.set(xmi_key, fragment_id)

        elif gate_owner:
            gate_id = f"{message_id}_{key}"
            gate_elem = find_element_by_id(gate_id, parent_elem)
            if gate_elem is None:
                gate_parent = None
                gate_tag = message.get(key, {}).get("name")
                if gate_tag == None:
                    gate_tag = "formalGate"
                elif gate_tag != "formalGate":
                    gate_parent_id = gate_owner.get("idref", "")
                    gate_parent = find_element_by_id(gate_parent_id, parent_elem)
                if gate_parent is None:
                    gate_parent = parent_elem
                    
                gate_elem = create_sub_element(gate_parent, gate_tag, attrib={
                    etree.QName(namespaces["xmi"], "type"): "uml:Gate",
                    etree.QName(namespaces["xmi"], "id"): gate_id,
                    "visibility": "public"
                })

            gate_elem.set("message", message_id)
            message_elem.set(xmi_key, gate_id)

    create_boolean_values(message, message_elem)

    return message_elem

def create_fragment(fragment, parent_elem, diagram_used_elements=[]):
    if "id" not in fragment:
        fragment["id"] = gen_id()
    fragment_id = fragment["id"]

    fragment_elem = find_element_by_id(fragment_id, parent_elem)
    if fragment_elem is not None:
        return fragment_elem
    
    xmi_type = f"uml:{fragment.get('fragmentType', 'InteractionUse')}"
    fragment_elem = create_sub_element(parent_elem, "fragment", attrib={
        etree.QName(namespaces["xmi"], "type"): xmi_type,
        etree.QName(namespaces["xmi"], "id"): fragment_id,
        "name": fragment.get("name", ""),
        "visibility": "public"
     })

    interaction_operator = fragment.get("interactionOperator")
    if interaction_operator:
        fragment_elem.set("interactionOperator", interaction_operator)

    refers_to_id = fragment.get("refersTo", {}).get("idref")
    if refers_to_id:
        create_activity(
            {
                "id": refers_to_id,
                "name": fragment.get("refersTo", {}).get("name", ""),
                "isReentrant": False,
            },
            get_closest_package(parent_elem),
            xmi_type="uml:Interaction"
        )
        fragment_elem.set("refersTo", refers_to_id)

    for covered_lifeline_id in fragment.get("coveredLifelines", []):
        create_sub_element(fragment_elem, "covered", attrib={
            etree.QName(namespaces["xmi"], "idref"): covered_lifeline_id
        })

        lifeline_elem = find_element_by_id(covered_lifeline_id, parent_elem)
        if lifeline_elem is not None:
            covered_bys = lifeline_elem.findall("coveredBy")
            found = False
            for covered_by in covered_bys:
                if get_attribute_with_ns("idref", covered_by) == fragment_id:
                    found = True
                    break
            if not found:
                create_sub_element(lifeline_elem, "coveredBy", attrib={
                    etree.QName(namespaces["xmi"], "idref"): fragment_id
                })

    invariant = fragment.get("invariant")
    if invariant:
        if "id" not in invariant:
            invariant["id"] = f"{fragment_id}_invariant"
        invariant_id = invariant["id"]
        invariant_elem = create_sub_element(fragment_elem, "invariant", attrib={
            etree.QName(namespaces["xmi"], "type"): "uml:Constraint",
            etree.QName(namespaces["xmi"], "id"): invariant_id,
            "name": invariant.get("name", "")
        })
        state_id = invariant.get("state", {}).get("idref")
        state_name = invariant.get("state", {}).get("name", "")
        if state_id:
            xmi_extension_elem = create_sub_element(
                invariant_elem,
                etree.QName(namespaces["xmi"], "Extension"),
                attrib={"extender": "MagicDraw UML 2024x"}
            )
            model_extension_elem = create_sub_element(xmi_extension_elem, "modelExtension")
            create_sub_element(model_extension_elem, "specification", attrib={
                etree.QName(namespaces["xmi"], "type"): "uml:ElementValue",
                etree.QName(namespaces["xmi"], "id"): f"{invariant_id}_specification",
                "element": state_id
            })

            # Ensure the referred state invariant element exists
            if len(fragment.get("coveredLifelines", [])) == 1 and lifeline_elem is not None:
                state_parent_id = find_element_by_id(
                    lifeline_elem.get("represents"), parent_elem,
                    top_node=find_root_model(parent_elem.getroottree()),
                    fallback={}
                ).get("type")
                if state_parent_id:
                    state_parent_elem = find_element_by_id(
                        state_parent_id, parent_elem,
                        top_node=find_root_model(parent_elem.getroottree())
                    )
                    if state_parent_elem is not None:
                        state_machine_id = f"{state_parent_id}_stateMachine"
                        state_machine_elem = find_element_by_id(state_machine_id, parent_elem)
                        if state_machine_elem is None:
                            state_machine_elem = create_sub_element(state_parent_elem, "ownedBehavior", attrib={
                                etree.QName(namespaces["xmi"], "type"): "uml:StateMachine",
                                etree.QName(namespaces["xmi"], "id"): state_machine_id,
                                "name": state_parent_elem.get("name", "")
                            })
                            region_elem = create_sub_element(state_machine_elem, "region", attrib={
                                etree.QName(namespaces["xmi"], "type"): "uml:Region",
                                etree.QName(namespaces["xmi"], "id"): f"{state_machine_id}_region",
                                "visibility": "public"
                            })
                            create_sub_element(region_elem, "subvertex", attrib={
                                etree.QName(namespaces["xmi"], "type"): "uml:State",
                                etree.QName(namespaces["xmi"], "id"): state_id,
                                "name": state_name,
                                "visibility": "public",
                            })

    for operand in fragment.get("operands", []):
        create_interaction_operand(operand, fragment_elem, diagram_used_elements)

    create_boolean_values(fragment, fragment_elem)

    return fragment_elem

def create_interaction_operand(operand, parent_elem, diagram_used_elements=[]):
    if "id" not in operand:
        operand["id"] = gen_id()
    operand_id = operand["id"]

    operand_elem = find_element_by_id(operand_id, parent_elem)
    if operand_elem is None:
        operand_elem = create_sub_element(parent_elem, "operand", attrib={
            etree.QName(namespaces["xmi"], "type"): "uml:InteractionOperand",
            etree.QName(namespaces["xmi"], "id"): operand_id,
            "name": operand.get("name", ""),
            "visibility": "public"
        })
    for nested_fragment in operand.get("nestedFragments", []):
        create_fragment(nested_fragment, operand_elem, diagram_used_elements)
        diagram_used_elements.append({"element": nested_fragment, "element_class": "Fragment"})

    guard = operand.get("guard")
    if guard:
        guard_elem = create_sub_element(operand_elem, "guard", attrib={
            etree.QName(namespaces["xmi"], "type"): "uml:InteractionConstraint",
            etree.QName(namespaces["xmi"], "id"): f"{operand_id}_guard"
        })

        specification_elem = create_sub_element(guard_elem, "specification", attrib={
            etree.QName(namespaces["xmi"], "type"): "uml:OpaqueExpression",
            etree.QName(namespaces["xmi"], "id"): f"{operand_id}_guard_specification"
        })

        if isinstance(guard, dict):
            for key in ("language", "body"):
                if key in guard:
                    key_elem = create_sub_element(specification_elem, key)
                    key_elem.text = guard[key]
        else:
            specification_elem.set(etree.QName(namespaces["xmi"], "type"), "uml:LiteralString")
            specification_elem.set("value", str(guard))

    create_boolean_values(operand, operand_elem)

    diagram_used_elements.append({"element": operand, "element_class": "InteractionOperand"})

def create_sd_constraint(constraint, parent_elem):
    if "id" not in constraint:
        constraint["id"] = gen_id()
    constraint_id = constraint["id"]

    constraint_elem = find_element_by_id(constraint_id, parent_elem)
    if constraint_elem is not None:
        return constraint_elem
    
    xmi_type = f"uml:{constraint.get('type', 'Constraint')}"
    constraint_elem = create_sub_element(parent_elem, "ownedRule", attrib={
        etree.QName(namespaces["xmi"], "type"): xmi_type,
        etree.QName(namespaces["xmi"], "id"): constraint_id,
        "name": constraint.get("name", "")
    })
    
    constrained_elements = constraint.get("constrainedElements", [])
    for constrained_element in constrained_elements:
        constrained_element_id = constrained_element.get("idref")
        if not constrained_element_id:
            continue
        first_event = constrained_element.get("firstEvent", False)
        if len(constrained_elements) == 1:
            constraint_elem.set("firstEvent", smart_uncast(first_event))
        else:
            first_event_elem = create_sub_element(constraint_elem, "firstEvent")
            first_event_elem.text = smart_uncast(first_event)
        
        create_sub_element(constraint_elem, "constrainedElement", attrib={
            etree.QName(namespaces["xmi"], "idref"): constrained_element_id
        })

    specification_elem = create_sub_element(constraint_elem, "specification", attrib={
        etree.QName(namespaces["xmi"], "type"): xmi_type.replace("Constraint", "Interval"),
        etree.QName(namespaces["xmi"], "id"): f"{constraint_id}_specification"
    })
    parent_pkg = get_closest_package(parent_elem)

    for key in ("max", "min"):
        # Time Event
        time_event_id = f"{constraint_id}_{key}"
        time_event_elem = create_sub_element(parent_pkg, "packagedElement", attrib={
            etree.QName(namespaces["xmi"], "type"): "uml:TimeEvent",
            etree.QName(namespaces["xmi"], "id"): time_event_id,
        })
        when_elem = create_sub_element(time_event_elem, "when", attrib={
            etree.QName(namespaces["xmi"], "type"): "uml:TimeExpression",
            etree.QName(namespaces["xmi"], "id"): f"{time_event_id}_when"
        })
        key_parent = when_elem
        if xmi_type == "uml:DurationConstraint":
            expr_elem = create_sub_element(when_elem, "expr", attrib={
                etree.QName(namespaces["xmi"], "type"): "uml:Duration",
                etree.QName(namespaces["xmi"], "id"): f"{time_event_id}_when_expr"
            })
            key_parent = expr_elem

        # Time Observation
        observation_elem = create_sub_element(parent_elem, "observation", attrib={
            etree.QName(namespaces["xmi"], "type"): xmi_type.replace("Constraint", "Observation"),
            etree.QName(namespaces["xmi"], "id"): gen_id()
        })

        if len(constrained_elements) == 1:
            observation_elem.set("event", constrained_elements[0].get("idref", ""))
        else:
            for constrained_element in constrained_elements:
                create_sub_element(observation_elem, "event", attrib={
                    etree.QName(namespaces["xmi"], "idref"): constrained_element.get("idref", "")
                })

        create_sub_element(key_parent, "observation", attrib={
            etree.QName(namespaces["xmi"], "idref"): get_attribute_with_ns("id", observation_elem)
        })

        if key in constraint:
            create_sub_element(key_parent, "expr", attrib={
                etree.QName(namespaces["xmi"], "type"): "uml:LiteralString",
                etree.QName(namespaces["xmi"], "id"): f"{time_event_id}_when_expr_value",
                "value": str(constraint[key])
            })
        
        specification_elem.set(key, get_attribute_with_ns("id", key_parent))

    return constraint_elem