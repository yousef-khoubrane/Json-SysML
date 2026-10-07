

from utils.helpers import namespaces, gen_id
from utils.getter_utils import (
    find_element_by_id,
    find_root_model,
    get_attribute_with_ns,
    get_closest_package,
)
from utils.common_utils import (
    create_sub_element,
    create_element,
    create_boolean_values,
    create_stereotypes,
    create_type,
    update_created_nodes,
)
from utils.bdd_utils import create_port, create_property, create_parameter

from lxml import etree

def create_activity(activity, parent_elem, xmi_type="uml:Activity", override_existing=True):
    model_elem = find_root_model(parent_elem.getroottree().getroot())
    if "id" not in activity:
        activity["id"] = gen_id()

    act_elem = find_element_by_id(activity["id"], parent_elem, top_node=model_elem)
    tag = "ownedBehavior"
    if get_attribute_with_ns("type", parent_elem) in ["uml:Package", "uml:Model"]:
        tag = "packagedElement"
        
    if act_elem is None:
        act_elem = create_sub_element(parent_elem, tag, attrib={
            etree.QName(namespaces["xmi"], "type"): xmi_type,
            etree.QName(namespaces["xmi"], "id"): activity["id"],
            "name": activity.get("name", "")
        })
    elif not override_existing:
        return act_elem
    else:
        act_elem.set(etree.QName(namespaces["xmi"], "type"), xmi_type)
        act_elem.set("name", activity.get("name", ""))
    if act_elem is not parent_elem:
        try:
            parent_elem.append(act_elem)
        except Exception:
            pass
        act_elem.tag = tag
        closest_package = get_closest_package(parent_elem)
        for elem in act_elem:
            if get_attribute_with_ns("type", elem) == "uml:Activity":
                elem.tag = "ownedBehavior"
            elif get_attribute_with_ns("type", elem) == "uml:Class":
                closest_package.append(elem)
            elif elem.tag == "packagedElement":
                elem.tag = "nestedClassifier"

    if "TestCase" in activity.get("stereotypes", []):
        verdict_param_exists = False
        verdict_param_id = f"{activity['id']}_verdict_parameter"
        for param in activity.get("parameters", []):
            param_type = param.get("type", {})
            if "idref" not in param_type and param_type.get("name") == "VerdictKind":
                verdict_param_exists = True
                if "id" not in param:
                    param["id"] = verdict_param_id
        if not verdict_param_exists:
            activity.setdefault("parameters", []).append({
                "name": "verdict",
                "id": verdict_param_id,
                "direction": "return",
                "type": {"name": "VerdictKind"}
            })

    for param in activity.get("parameters", []):
        create_parameter(param, act_elem, create_activity_parameter_node=True)

    for prop in activity.get("properties", []):
        create_property(prop, act_elem)

    for port in activity.get("ports", []):
        create_port(port, act_elem)

    if "isReentrant" not in activity:
        activity["isReentrant"] = False
    create_boolean_values(activity, act_elem)

    create_stereotypes(
        activity["id"],
        activity.get("stereotypes", []),
        act_elem.getroottree().getroot(),
        tagged_values=activity.get("taggedValues", {})
    )

    return act_elem

valid_action_types = [
    "AcceptCallAction", "AcceptEventAction", "AddStructuralFeatureValueAction",
    "AddVariableValueAction", "BroadcastSignalAction", "CallAction",
    "CallBehaviorAction", "CallOperationAction", "ClearAssociationAction",
    "ClearStructuralFeatureAction", "ClearVariableAction", "CreateLinkAction",
    "CreateLinkObjectAction", "CreateObjectAction", "DestroyLinkAction",
    "DestroyObjectAction", "ExpansionRegion", "InvocationAction", "LinkAction",
    "OpaqueAction", "RaiseExceptionAction", "ReadExtentAction", "ReadIsClassifiedObjectAction",
    "ReadLinkAction", "ReadLinkObjectEndAction", "ReadLinkObjectEndQualifierAction",
    "ReadSelfAction", "ReadStructuralFeatureAction", "ReadVariableAction",
    "ReclassifyObjectAction", "ReduceAction", "RemoveStructuralFeatureValueAction",
    "RemoveVariableValueAction", "ReplyAction", "SendObjectAction",
    "SendSignalAction", "SequenceNode", "StartClassifierBehaviorAction",
    "StartObjectBehaviorAction", "StructuralFeatureAction", "TestIdentityAction",
    "UnmarshallAction", "ValueSpecificationAction", "VariableAction", "WriteLinkAction",
    "WriteStructuralFeatureAction", "WriteVariableAction"
]
def create_action(action, parent_elem, diagram_used_elements=None):
    if "id" not in action:
        action["id"] = gen_id()

    action_elem = find_element_by_id(action["id"], parent_elem)
    if action_elem is not None:
        return action_elem
    
    xmi_type = "uml:CallBehaviorAction"
    action_type = action.get("type")
    if action_type in valid_action_types:
        xmi_type = f"uml:{action_type}"
    else:
        return None

    action_elem = create_sub_element(parent_elem, "node", attrib={
        etree.QName(namespaces["xmi"], "type"): xmi_type,
        etree.QName(namespaces["xmi"], "id"): action["id"],
        "name": action.get("name", ""),
        "visibility": "public"
    })

    behavior = action.get("behavior")
    if behavior:
        behavior_elem = create_activity(behavior, parent_elem)
        action_elem.set("behavior", get_attribute_with_ns("id", behavior_elem))

    for key in ("inputPins", "outputPins"):

        tag = "argument"
        pin_xmi_type = "uml:InputPin"
        param_direction = "in"
        if key == "outputPins":
            tag = "result"
            pin_xmi_type = "uml:OutputPin"
            param_direction = "out"

        for pin in action.get(key, []):
            if "id" not in pin:
                pin["id"] = gen_id()
            if pin.get("pinKind") in ("ValuePin", "ActionInputPin"):
                pin_xmi_type = f"uml:{pin.get('pinKind')}"
            pin_elem = create_sub_element(action_elem, tag, attrib={
                etree.QName(namespaces["xmi"], "type"): pin_xmi_type,
                etree.QName(namespaces["xmi"], "id"): pin.get("id"),
                "name": pin.get("name", ""),
                "visibility": "public"
            })
            create_type(pin.get("type"), pin_elem)
            sync_elem_idref = pin.get("syncElement", {}).get("idref")
            if sync_elem_idref:
                xmi_ext = create_sub_element(
                    pin_elem,
                    etree.QName(namespaces["xmi"], "Extension"),
                    attrib={"extender": "MagicDraw UML 2024x"}
                )
                create_sub_element(
                    xmi_ext, "modelExtension",
                    attrib={"syncElement": sync_elem_idref}
                )
                create_parameter({
                    "name": pin.get("name", ""),
                    "id": sync_elem_idref,
                    "direction": param_direction
                }, parent_elem, create_activity_parameter_node=True)
            if diagram_used_elements:
                diagram_used_elements.append({"element": pin, "element_class": "Pin"})

    create_boolean_values(action, action_elem)

    create_stereotypes(
        action["id"],
        action.get("stereotypes", []),
        parent_elem.getroottree().getroot()
    )

valid_node_types = [
    "InitialNode", "ForkNode", "JoinNode", "ActivityFinalNode", "DecisionNode",
    "MergeNode", "FlowFinalNode", "ActivityParameterNode", "DataStoreNode",
    "CentralBufferNode", "ConditionalNode", "LoopNode", "SequenceNode",
    "StructuredActivityNode"
]
def create_node(node, parent_elem):
    if "id" not in node:
        node["id"] = gen_id()

    node_elem = find_element_by_id(node["id"], parent_elem)
    if node_elem is not None:
        return node_elem
    
    xmi_type = "uml:InitialNode"
    node_type = node.get("nodeType")
    if node_type in valid_node_types:
        xmi_type = f"uml:{node_type}"
    else:
        return None

    node_elem = None

    param_idref = node.get("parameter", {}).get("idref")
    if param_idref:
        node_elem = parent_elem.find(f"./node[@parameter='{param_idref}']")
        if node_elem is not None:
            node_elem.set("name", node.get("name", node_elem.get("name", "")))
            node_elem.set(etree.QName(namespaces["xmi"], "type"), xmi_type)
            old_id = get_attribute_with_ns("id", node_elem)
            if old_id != node["id"]:
                node_elem.set(etree.QName(namespaces["xmi"], "id"), node["id"])
                update_created_nodes(remove=[old_id], add={node["id"]: node_elem})

    if node_elem is None:
        node_elem = create_sub_element(parent_elem, "node", attrib={
            etree.QName(namespaces["xmi"], "type"): xmi_type,
            etree.QName(namespaces["xmi"], "id"): node["id"],
            "name": node.get("name", ""),
            "visibility": "public"
        })

    if param_idref:
        node_elem.set("parameter", param_idref)
        param_elem = find_element_by_id(param_idref, parent_elem)
        if param_elem is None:
            param = {"id": param_idref, **node.get("parameter")}
            create_parameter(param, parent_elem)

    create_boolean_values(node, node_elem)

    create_stereotypes(
        node["id"],
        node.get("stereotypes", []),
        parent_elem.getroottree().getroot()
    )

    if "type" in node:
        create_type(node["type"], node_elem)

    return node_elem

def create_edge(edge, parent_elem):
    source_id = edge.get("source", {}).get("idref")
    target_id = edge.get("target", {}).get("idref")
    if not source_id or not target_id:
        return None
    
    source_elem = find_element_by_id(source_id, parent_elem)
    target_elem = find_element_by_id(target_id, parent_elem)

    if source_elem is None or target_elem is None:
        return None

    if "id" not in edge:
        edge["id"] = gen_id()

    edge_elem = find_element_by_id(edge["id"], parent_elem)
    if edge_elem is not None:
        return edge_elem
    
    xmi_type = "uml:ControlFlow"
    if edge.get("type") == "ObjectFlow":
        xmi_type = "uml:ObjectFlow"
    
    edge_elem = create_sub_element(parent_elem, "edge", attrib={
        etree.QName(namespaces["xmi"], "type"): xmi_type,
        etree.QName(namespaces["xmi"], "id"): edge["id"],
        "name": edge.get("name", ""),
        "visibility": "public",
        "source": source_id,
        "target": target_id
    })

    return edge_elem

def create_partition(partition, parent_elem):
    if "id" not in partition:
        partition["id"] = gen_id()

    partition_elem = find_element_by_id(partition["id"], parent_elem)
    if partition_elem is not None:
        return partition_elem

    partition_elem = create_sub_element(parent_elem, "group", attrib={
        etree.QName(namespaces["xmi"], "type"): "uml:ActivityPartition",
        etree.QName(namespaces["xmi"], "id"): partition["id"],
        "name": partition.get("name", ""),
        "visibility": "public"
    })

    reference_exists = False
    for item in parent_elem.findall("partition"):
        if get_attribute_with_ns("idref", item) == partition["id"]:
            reference_exists = True
            break
    if not reference_exists:
        ref_elem = create_element("partition", attrib={
            etree.QName(namespaces["xmi"], "idref"): partition["id"],
        })
        parent_elem.insert(0, ref_elem)

    represented_idref = partition.get("representedElement", {}).get("idref")
    if represented_idref:
        partition_elem.set("represents", represented_idref)
        # Ensure the represented element exists
        pkg_elem = get_closest_package(parent_elem)
        represented_elem = find_element_by_id(
            represented_idref,
            pkg_elem,
            top_node=find_root_model(pkg_elem.getroottree()),
        )
        if represented_elem is None:
            represented_elem = create_property(
                {"id": represented_idref, **partition.get("representedElement", {})},
                parent_elem
            )

        for elem_id in partition.get("elements", []):
            in_partition_elem = find_element_by_id(elem_id, parent_elem)
            if in_partition_elem is not None:
                create_sub_element(in_partition_elem, "inPartition", attrib={
                    etree.QName(namespaces["xmi"], "idref"): partition["id"],
                })
                create_sub_element(partition_elem, in_partition_elem.tag, attrib={
                    etree.QName(namespaces["xmi"], "idref"): elem_id,
                })
                
                # Create allocations between the in-partition actions and the represented element
                if get_attribute_with_ns("type", in_partition_elem).endswith("Action"):
                    allocation_mode = "usage"
                    if (get_attribute_with_ns("type", represented_elem) != "uml:Property" 
                        or not partition.get("representedElement", {}).get("type", {}).get("idref")):
                        allocation_mode = "definition"

                    if allocation_mode == "usage":
                        # Action Allocation
                        action_allocation_id = f"{elem_id}__{represented_idref}"
                        action_allocation_elem = find_element_by_id(action_allocation_id, pkg_elem)
                        if action_allocation_elem is None:
                            action_allocation_elem = create_sub_element(pkg_elem, "packagedElement", attrib={
                                etree.QName(namespaces["xmi"], "type"): "uml:Abstraction",
                                etree.QName(namespaces["xmi"], "id"): action_allocation_id
                            })
                            create_sub_element(action_allocation_elem, "client", attrib={
                                etree.QName(namespaces["xmi"], "idref"): elem_id
                            })
                            create_sub_element(action_allocation_elem, "supplier", attrib={
                                etree.QName(namespaces["xmi"], "idref"): represented_idref
                            })
                            create_stereotypes(action_allocation_id, ["Allocate"], parent_elem.getroottree().getroot())

                    else:
                        # Behavior Allocation
                        behavior_id = in_partition_elem.get("behavior")
                        class_id = represented_idref
                        represented_type_id = partition.get("representedElement", {}).get("type", {}).get("idref")
                        if represented_type_id:
                            class_id = represented_type_id
                        behavior_elem = find_element_by_id(
                            behavior_id,
                            pkg_elem,
                            top_node=find_root_model(pkg_elem.getroottree())
                        )
                        if behavior_elem is None:
                            continue
                        behavior_allocation_id = f"{behavior_id}__{class_id}"
                        behavior_allocation_elem = find_element_by_id(behavior_allocation_id, pkg_elem)
                        if behavior_allocation_elem is None:
                            behavior_allocation_elem = create_sub_element(pkg_elem, "packagedElement", attrib={
                                etree.QName(namespaces["xmi"], "type"): "uml:Abstraction",
                                etree.QName(namespaces["xmi"], "id"): behavior_allocation_id
                            })
                            create_sub_element(behavior_allocation_elem, "client", attrib={
                                etree.QName(namespaces["xmi"], "idref"): behavior_id
                            })
                            create_sub_element(behavior_allocation_elem, "supplier", attrib={
                                etree.QName(namespaces["xmi"], "idref"): class_id
                            })
                            create_stereotypes(behavior_allocation_id, ["Allocate"], parent_elem.getroottree().getroot())

    create_boolean_values(partition, partition_elem)

    create_stereotypes(
        partition["id"],
        partition.get("stereotypes", []),
        parent_elem.getroottree().getroot()
    )

    return partition_elem

def create_interruptible_region(region, parent_elem):
    if "id" not in region:
        region["id"] = gen_id()

    region_elem = find_element_by_id(region["id"], parent_elem)
    if region_elem is not None:
        return region_elem

    region_elem = create_sub_element(parent_elem, "group", attrib={
        etree.QName(namespaces["xmi"], "type"): "uml:InterruptibleActivityRegion",
        etree.QName(namespaces["xmi"], "id"): region["id"],
        "name": region.get("name", ""),
        "visibility": "public"
    })

    for elem_id in region.get("interruptingEdges", []):
        edge_elem = find_element_by_id(elem_id, parent_elem)
        if edge_elem is not None:
            edge_elem.set("interrupts", region["id"])
            create_sub_element(region_elem, "interruptingEdge", attrib={
                etree.QName(namespaces["xmi"], "idref"): elem_id,
            })
    
    for elem_id in region.get("elements", []):
        elem = find_element_by_id(elem_id, parent_elem)
        if elem is not None:
            create_sub_element(elem, "inInterruptibleRegion", attrib={
                etree.QName(namespaces["xmi"], "idref"): region["id"],
            })
            create_sub_element(region_elem, elem.tag, attrib={
                etree.QName(namespaces["xmi"], "idref"): elem_id,
            })

    create_boolean_values(region, region_elem)

    create_stereotypes(
        region["id"],
        region.get("stereotypes", []),
        parent_elem.getroottree().getroot()
    )

    return region_elem