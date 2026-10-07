# MagicDraw-specific diagram utilities

from utils.helpers import namespaces, gen_id
from utils.getter_utils import find_element_by_id, find_root_model, get_attribute_with_ns
from utils.common_utils import create_sub_element
from utils.stm_utils import get_state_element_class
from utils.md_utils import move_nested_elements, set_md_element_properties
from utils.act_md_utils import get_action_element_class, get_node_element_class, update_act_geometry
from utils.sd_md_utils import update_sd_geometry

from lxml import etree

def add_md_owned_views(diagram, binary_object_id, used_elements, root):
    """
    Adds the "filePart" node that contains the MagicDraw-specific diagram information.

    Args:
        diagram (dict): The Json-SysML diagram.
        binary_object_id (str): The ID of the file part as referenced in the diagram extension in the logical model.
        used_elements (list): The list of used elements. Each element is a dictionary containing the element information and its class.
        root (etree.Element): The root element of the XMI document.
    """
    xmi_ext = create_sub_element(
        root, etree.QName(namespaces["xmi"], "Extension"),
        attrib={"extender": "MagicDraw UML 2024x"}
    )

    file_part = create_sub_element(xmi_ext, "filePart", attrib={
        "name": binary_object_id,
        "type": "XML",
        "header": "<?xml version='1.0' encoding='UTF-8'?>",
    })

    md_owned_views = create_sub_element(file_part, "mdOwnedViews")

    # Used Elements
    used_element_ids = [item.get("element", {}).get("id") or item.get("element", {}).get("idref") for item in used_elements]
    id_to_md_element_id = {}
    y_offset = 100
    x_offset = 50

    # Diagram Frame
    diagram_frame_id = gen_id()
    diagram_frame = create_sub_element(md_owned_views, "mdElement", attrib={
        "elementClass": "DiagramFrame",
        etree.QName(namespaces["xmi"], "id"): diagram_frame_id,
    })
    create_sub_element(diagram_frame, "elementID", attrib={
        etree.QName(namespaces["xmi"], "idref"): diagram.get("id")
    })
    create_sub_element(diagram_frame, "geometry").text = "5, 5, 700, 600"
    id_to_md_element_id[diagram.get("id")] = {0: diagram_frame_id}

    # ============================================================================
    # First Pass: Create MD elements for each used element.
    # ============================================================================
    for item in used_elements:
        elem = item.get("element", {})
        element_class = item.get("element_class")
        idref = elem.get("id") if "id" in elem else elem.get("idref")
        if idref is None or element_class is None:
            continue
        md_element_id = gen_id()
        mapping = {0: md_element_id}
        if elem.get("portOwnerIdref"):
            mapping[elem.get("portOwnerIdref")] = md_element_id
        id_to_md_element_id.setdefault(idref, {}).update(mapping)

        md_element = create_sub_element(md_owned_views, "mdElement", attrib={
            "elementClass": element_class,
            etree.QName(namespaces["xmi"], "id"): md_element_id,
        })

        if element_class not in ["ContainmentLink"]:
            create_sub_element(md_element, "elementID", attrib={
                etree.QName(namespaces["xmi"], "idref"): idref
            })

        if element_class in [
            "Class", "Package", "Comment", "Actor", "Interface", "Signal", "UseCase",
            "DiagramShape", "DataType", "InstanceSpecification", "Part", "Action", "Node",
            "Enumeration", "State"
        ]:
            create_sub_element(md_element, "geometry").text = f"{x_offset}, {y_offset}, 0, 0"
            x_offset += 150
            if x_offset > 600:  # Reset to next row
                x_offset = 50
                y_offset += 150

            if element_class == "Comment" and "annotated_element_ids" in elem:
                for annotated_elem_id in elem["annotated_element_ids"]:
                    if annotated_elem_id not in id_to_md_element_id:
                        continue
                    note_anchor_elem = create_sub_element(md_owned_views, "mdElement", attrib={
                        "elementClass": "NoteAnchor",
                        etree.QName(namespaces["xmi"], "id"): gen_id()
                    })
                    create_sub_element(note_anchor_elem, "linkFirstEndID", attrib={
                        etree.QName(namespaces["xmi"], "idref"): md_element_id
                    })
                    create_sub_element(note_anchor_elem, "linkSecondEndID", attrib={
                        etree.QName(namespaces["xmi"], "idref"): id_to_md_element_id.get(annotated_elem_id)[0]
                    })

            elif element_class == "Part" and elem.get("shortcutPath"):
                nested_parts = "^".join([prop["idref"] for prop in elem.get("shortcutPath", []) if "idref" in prop])
                create_sub_element(md_element, "nestedParts", attrib={
                    etree.QName(namespaces["xmi"], "value"): nested_parts
                })

            elif element_class == "Action":
                md_element.set("elementClass", get_action_element_class(elem))

            elif element_class == "Node":
                md_element.set("elementClass", get_node_element_class(elem))

            elif element_class == "State" and elem.get("type") != "State":
                md_element.set("elementClass", get_state_element_class(elem))

        elif element_class in [
            "Association", "Generalization", "ContainmentLink", "AssociationClass", "PackageImport",
            "Dependency", "Extend", "Include", "Connector", "ControlFlow", "Transition",
            "SeqMessage", "SDConstraint"
        ]:
            if element_class == "ControlFlow" and elem.get("type") == "ObjectFlow":
                md_element.set("elementClass", "ObjectFlow")

            elif element_class == "SeqMessage":
                y_offset += 50
                # Gates
                for key in ("source", "target"):
                    gate_owner = elem.get(key, {}).get("gateOwner")
                    if gate_owner:
                        if elem.get(key, {}).get("name") == "formalGate":
                            elem[key]["idref"] = diagram.get("id")
                        elif gate_owner.get("idref"):
                            elem[key]["idref"] = gate_owner["idref"]
                if elem.get("source", {}).get("idref") == elem.get("target", {}).get("idref"):
                    md_element.set("elementClass", "SeqSelfMessage")
                create_sub_element(md_element, "geometry").text = f"0, {y_offset}, 40, {y_offset}"
                        
            elif element_class == "SDConstraint":
                constraint_type = elem.get("type", "Constraint")
                md_element.set("elementClass", constraint_type)
                constrained_elements = elem.get("constrainedElements", [])
                for constrained_element in constrained_elements:
                    message_md_element_id = id_to_md_element_id.get(constrained_element.get("idref", ""), [""])[0]
                    if message_md_element_id:
                        message_md_element = find_element_by_id(message_md_element_id, md_owned_views)
                        if message_md_element is not None:
                            constraints_compartment = message_md_element.find("./compartment[@compartmentID='CONSTRAINTS']")
                            if constraints_compartment is None:
                                create_sub_element(message_md_element, "compartment", attrib={
                                    etree.QName(namespaces["xmi"], "value"): idref,
                                    "compartmentID": "CONSTRAINTS"
                                })
                            else:
                                xmi_value = get_attribute_with_ns("value", constraints_compartment, fallback="")
                                if xmi_value != "":
                                    xmi_value = f"{xmi_value}^{idref}"
                                else:
                                    xmi_value = idref
                                constraints_compartment.set(etree.QName(namespaces["xmi"], "value"), xmi_value)
                if constraint_type != "DurationConstraint" or len(constrained_elements) != 2:
                    continue
                for i, key in enumerate(["source", "target"]):
                    elem[key] = constrained_elements[i]

            source_end_id_idx = 0
            target_end_id_idx = 0
            if element_class == "Connector" and len(elem.get("ends", [])) == 2:
                source_id, target_id = [end.get("idref") for end in elem.get("ends")]
                source_end_id_idx = elem["ends"][0].get("portOwnerIdref", 0)
                target_end_id_idx = elem["ends"][1].get("portOwnerIdref", 0)
                if source_end_id_idx not in id_to_md_element_id.get(source_id, {}):
                    source_end_id_idx = 0
                if target_end_id_idx not in id_to_md_element_id.get(target_id, {}):
                    target_end_id_idx = 0
            else:
                source_id = elem.get("source", {}).get("idref", elem.get("source", {}).get("originalID"))
                target_id = elem.get("target", {}).get("idref", elem.get("target", {}).get("originalID"))

            if source_id not in id_to_md_element_id or target_id not in id_to_md_element_id:
                continue

            if element_class == "SeqMessage":
                source_id, target_id = target_id, source_id

            create_sub_element(md_element, "linkFirstEndID", attrib={
                etree.QName(namespaces["xmi"], "idref"): id_to_md_element_id.get(source_id)[source_end_id_idx]
            })
            create_sub_element(md_element, "linkSecondEndID", attrib={
                etree.QName(namespaces["xmi"], "idref"): id_to_md_element_id.get(target_id)[target_end_id_idx]
            })

            if element_class == "ContainmentLink":
                continue

            compartments = {}
            for suffix in ["A", "B"]:
                compartments[suffix] = create_sub_element(md_element, "compartment", attrib={
                    "compartmentID": f"CONVEYED_INFORMATION_{suffix}",
                    "isContentLocked": "true"
                })

            create_sub_element(md_element, "nameVisible", attrib={
                etree.QName(namespaces["xmi"], "value"): "true"
            })
            
            ### This is to show item flows names
            def get_item_flow_tag(x):
                num_to_suffix = {0: "A", 1: "B"}
                ends = elem.get("ends", [{}, {}])
                for i in range(2):
                    if x.get("sourceIdref", "not_found") in [ends[i].get("type", {}).get("idref"), ends[i].get("idref")]:
                        return f"linkConveyed{num_to_suffix[i]}ID"
                return "linkConveyedAID"
            
            get_item_flow_name = lambda x: f"{x.get('itemProperty', {}).get('name', '')} : {x['conveyed'].get('name', '')}"
            item_flows = {
                get_item_flow_tag(item): item
                for item in elem.get("itemFlows", [])
                if "targetIdref" in item and "conveyed" in item
            }
            ###

            association_md_owned_views = create_sub_element(md_element, "mdOwnedViews")
            role_ids = []

            if "member_end_ids" in elem:
                end_element_class = "ConnectorEnd" if element_class == "Connector" else "Role"
                elem["member_end_ids"] = elem["member_end_ids"][::-1]
                for end_id in elem["member_end_ids"]:
                    role_md_element_id = gen_id()
                    role_ids.append(role_md_element_id)
                    role_md_element = create_sub_element(association_md_owned_views, "mdElement", attrib={
                        "elementClass": end_element_class,
                        etree.QName(namespaces["xmi"], "id"): role_md_element_id,
                    })
                    create_sub_element(role_md_element, "elementID", attrib={
                        etree.QName(namespaces["xmi"], "idref"): end_id
                    })

                for i, role_id in enumerate(role_ids):
                    if element_class == "Connector":
                        end_ref_name = "connectorEndAID" if i == 0 else "connectorEndBID"
                    else:
                        end_ref_name = "associationFirstEndID" if i == 0 else "associationSecondEndID"
                    create_sub_element(md_element, end_ref_name, attrib={
                        etree.QName(namespaces["xmi"], "idref"): role_id
                    })

                ### This is to show item flows names
                for tag, item_flow in item_flows.items():
                    name = get_item_flow_name(item_flow)
                    text_box_id = gen_id()
                    text_box_elem = create_sub_element(association_md_owned_views, "mdElement", attrib={
                        "elementClass": "TextBox",
                        etree.QName(namespaces["xmi"], "id"): text_box_id,
                    })
                    create_sub_element(text_box_elem, "text").text = name
                    create_sub_element(md_element, tag, attrib={
                        etree.QName(namespaces["xmi"], "idref"): text_box_id
                    })
                    compartments[tag[-3]].set(etree.QName(namespaces["xmi"], "value"), item_flow.get("conveyed", {}).get("idref", ""))
                ###

            if element_class == "AssociationClass":
                assoc_class_md_element_id = gen_id()
                assoc_class_md_element = create_sub_element(association_md_owned_views, "mdElement", attrib={
                    "elementClass": "Class",
                    etree.QName(namespaces["xmi"], "id"): assoc_class_md_element_id,
                })
                create_sub_element(assoc_class_md_element, "elementID", attrib={
                    etree.QName(namespaces["xmi"], "idref"): idref
                })
                
                create_sub_element(assoc_class_md_element, "geometry").text = f"{x_offset}, {y_offset}, 100, 50"
                x_offset += 150
                if x_offset > 600:  # Reset to next row
                    x_offset = 50
                    y_offset += 150
                assoc_link_md_element = create_sub_element(association_md_owned_views, "mdElement", attrib={
                    "elementClass": "LinkAttribute",
                    etree.QName(namespaces["xmi"], "id"): gen_id(),
                })
                create_sub_element(assoc_link_md_element, "elementID", attrib={
                    etree.QName(namespaces["xmi"], "idref"): idref
                })
                create_sub_element(assoc_link_md_element, "linkFirstEndID", attrib={
                    etree.QName(namespaces["xmi"], "idref"): md_element_id
                })
                create_sub_element(assoc_link_md_element, "linkSecondEndID", attrib={
                    etree.QName(namespaces["xmi"], "idref"): assoc_class_md_element_id
                })

        elif element_class == "SwimlaneHeader":
            swimlane_elem = md_owned_views.find(f"./mdElement[@elementClass='Swimlane']")
            if swimlane_elem is None:
                swimlane_elem = create_sub_element(md_owned_views, "mdElement", attrib={
                    "elementClass": "Swimlane",
                    etree.QName(namespaces["xmi"], "id"): gen_id(),
                })
            # Set allocation mode to Usage instead of definition
            set_md_element_properties(swimlane_elem, [
                {"propertyID": "ALLOCATION_MODE_ID", "value": "1", "elementClass": "ChoiceProperty"}
            ])
            
            swimlane_md_owned_views = swimlane_elem.find("mdOwnedViews")
            if swimlane_md_owned_views is None:
                swimlane_md_owned_views = create_sub_element(swimlane_elem, "mdOwnedViews")
            swimlane_md_owned_views.append(md_element)

        elif element_class == "SequenceLifeline":
            lifeline_md_owned_views = md_element.find("mdOwnedViews")
            if lifeline_md_owned_views is None:
                lifeline_md_owned_views = create_sub_element(md_element, "mdOwnedViews")

            lifelineline = lifeline_md_owned_views.find(f"./mdElement[@elementClass='LifeLineLine']")
            if lifelineline is None:
                lifelineline = create_sub_element(lifeline_md_owned_views, "mdElement", attrib={
                    "elementClass": "LifeLineLine",
                    etree.QName(namespaces["xmi"], "id"): gen_id(),
                })
                create_sub_element(lifelineline, "elementID", attrib={
                    etree.QName(namespaces["xmi"], "idref"): idref
                })
            id_to_md_element_id[idref]["lifelineline"] = get_attribute_with_ns("id", lifelineline)

            lll_owned_views = lifelineline.find("mdOwnedViews")
            if lll_owned_views is None:
                lll_owned_views = create_sub_element(lifelineline, "mdOwnedViews")
            activation = lll_owned_views.find(f"./mdElement[@elementClass='Activation']")
            if activation is None:
                activation = create_sub_element(lll_owned_views, "mdElement", attrib={
                    "elementClass": "Activation",
                    etree.QName(namespaces["xmi"], "id"): gen_id(),
                })
                create_sub_element(activation, "elementID", attrib={
                    etree.QName(namespaces["xmi"], "idref"): idref
                })
            id_to_md_element_id[idref][0] = get_attribute_with_ns("id", activation)

        elif element_class == "Fragment":
            frag_elem_class = elem.get("fragmentType")
            if frag_elem_class not in ["InteractionUse", "StateInvariant", "CombinedFragment"]:
                frag_elem_class = "CombinedFragment"
            md_element.set("elementClass", frag_elem_class)
            y_offset += 50
            create_sub_element(md_element, "geometry").text = f"50, {y_offset}, 0, 0"

        elif element_class == "Pin":
            set_md_element_properties(md_element, [
                {"propertyID": "SHOW_TYPE", "value": "true", "elementClass": "BooleanProperty"}
            ])

    # ============================================================================
    # Second Pass: Move nested elements under their respective parent elements.
    # ============================================================================
    for item in used_elements:
        element_class = item.get("element_class")
        if element_class not in [
            "Package", "Class", "Part", "Action", "SwimlaneHeader", "InterruptibeActivityRegion",
            "Region", "State", "Fragment", "InteractionOperand", "SDConstraint"
        ]:
            continue
        elem = item.get("element", {})
        idref = elem.get("id") if "id" in elem else elem.get("idref")
        if idref is None or element_class is None:
            continue

        md_element = find_element_by_id(id_to_md_element_id.get(idref)[0], md_owned_views)
        if md_element is None:
            continue

        if element_class == "Package":
            if "ownedUseCases" in elem:
                move_nested_elements(md_element, elem["ownedUseCases"], id_to_md_element_id, md_owned_views)
            else:
                pkg_elem = find_element_by_id(idref, find_root_model(root))
                if pkg_elem is not None:
                    to_ignore = [
                        relationship.get("target", {}).get("idref") for relationship in diagram.get("relationships", [])
                        if relationship.get("type") == "Containment" and relationship.get("source", {}).get("idref") == idref
                    ]
                    nested_elements = []
                    for used_elem_id in list(set(used_element_ids) - set(to_ignore)):
                        nested_elem = pkg_elem.find(f"./*[@xmi:id='{used_elem_id}']", namespaces=namespaces)
                        if nested_elem is not None:
                            nested_elements.append(used_elem_id)
                    move_nested_elements(md_element, nested_elements, id_to_md_element_id, md_owned_views)

        elif element_class == "Class":
            if "ownedUseCases" in elem:
                set_md_element_properties(md_element, [
                    {"propertyID": "SUPPRESS_REFERENCES_COMPARTMENT", "value": "true", "elementClass": "BooleanProperty"},
                    {"propertyID": "SUPPRESS_PARTS_COMPARTMENT", "value": "true", "elementClass": "BooleanProperty"},
                    {"propertyID": "SUPPRESS_PROXYPORTS_COMPARTMENT", "value": "true", "elementClass": "BooleanProperty"},
                    {"propertyID": "SUPPRESS_PROPERTIES_COMPARTMENT", "value": "true", "elementClass": "BooleanProperty"},
                ])
                move_nested_elements(md_element, elem["ownedUseCases"], id_to_md_element_id, md_owned_views)

        elif element_class == "Part":
            if "nestedProperties" in elem:
                nested_properties_ids = [prop["id"] for prop in elem["nestedProperties"] if "id" in prop]
                move_nested_elements(md_element, nested_properties_ids, id_to_md_element_id, md_owned_views, move_under="parts")
            if "ports" in elem:
                move_nested_elements(md_element, elem["ports"], id_to_md_element_id, md_owned_views)
        
        elif element_class == "Action":
            pins_to_move = [pin["id"] for key in ("inputPins", "outputPins") for pin in elem.get(key, []) if "id" in pin]
            if pins_to_move:
                move_nested_elements(md_element, pins_to_move, id_to_md_element_id, md_owned_views)
        
        elif element_class == "SwimlaneHeader" and elem.get("elements"):
            swimlane_cell_elem = create_sub_element(md_element.getparent(), "mdElement", attrib={
                "elementClass": "SwimlaneCell",
                etree.QName(namespaces["xmi"], "id"): gen_id(),
            })
            move_nested_elements(swimlane_cell_elem, elem["elements"], id_to_md_element_id, md_owned_views)

        elif element_class == "InterruptibeActivityRegion" and elem.get("elements"):
            move_nested_elements(md_element, elem["elements"], id_to_md_element_id, md_owned_views)
        
        elif element_class == "Region" and elem.get("nestedVertices"):
            move_nested_elements(md_element, elem["nestedVertices"], id_to_md_element_id, md_owned_views)
        
        elif element_class == "State":
            if elem.get("regions"):
                region_ids = [f"{idref}_region{i+1}" for i in range(len(elem.get("regions", [])))]
                move_nested_elements(md_element, region_ids, id_to_md_element_id, md_owned_views, move_under="regions")
            if elem.get("connectionPoints"):
                cp_ids = [item["id"] for item in elem.get("connectionPoints") if "id" in item]
                move_nested_elements(md_element, cp_ids, id_to_md_element_id, md_owned_views)

        elif element_class == "Fragment":
            if elem.get("operands"):
                operand_ids = [operand["id"] for operand in elem["operands"] if "id" in operand]
                move_nested_elements(md_element, operand_ids, id_to_md_element_id, md_owned_views, move_under="operands")

            if elem.get("fragmentType") == "StateInvariant" and len(elem.get("coveredLifelines", [])) == 1:
                lifeline_idref = elem["coveredLifelines"][0]
                if lifeline_idref in id_to_md_element_id:
                    lifelineline_md_element_id = id_to_md_element_id[lifeline_idref]["lifelineline"]
                    lifelineline_md_element = find_element_by_id(lifelineline_md_element_id, md_owned_views)
                    if lifelineline_md_element is not None:
                        move_nested_elements(lifelineline_md_element, [idref], id_to_md_element_id, md_owned_views)

        elif element_class == "InteractionOperand" and elem.get("nestedFragments"):
            nested_fragment_ids = [fragment["id"] for fragment in elem["nestedFragments"] if "id" in fragment]
            move_nested_elements(md_element, nested_fragment_ids, id_to_md_element_id, md_owned_views)

        elif element_class == "SDConstraint" and elem.get("type") == "TimeConstraint":
            message_md_element = find_element_by_id(
                id_to_md_element_id.get(
                    elem.get("constrainedElements", [{}])[0].get("idref", ""),
                    [""]
                )[0],
                md_owned_views
            )
            if message_md_element is not None:
                move_nested_elements(message_md_element, [idref], id_to_md_element_id, md_owned_views)

    if diagram.get("context", {}).get("ports"):
        move_nested_elements(diagram_frame, diagram["context"]["ports"], id_to_md_element_id, md_owned_views)
    
    if diagram.get("nodes"):
        nodes_to_move = [node["id"] for node in diagram["nodes"] if "id" in node and node.get("type") == "ActivityParameterNode"]
        move_nested_elements(diagram_frame, nodes_to_move, id_to_md_element_id, md_owned_views)
    
    if diagram.get("connectionPoints"):
        cp_ids = [item["id"] for item in diagram.get("connectionPoints") if "id" in item]
        move_nested_elements(diagram_frame, cp_ids, id_to_md_element_id, md_owned_views)

    # ============================================================================
    # Finally: Update geometry for Sequence and Activity diagrams.
    # ============================================================================
    if diagram.get("diagramType") == "sd":
        update_sd_geometry(file_part)
    elif diagram.get("diagramType") == "act":
        update_act_geometry(file_part)