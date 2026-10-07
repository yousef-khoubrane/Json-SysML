
from utils.helpers import (
    namespaces,
    diagram_full_types,
    diagram_uml_types,
    get_diagram_required_features,
    gen_id,
)
from utils.getter_utils import find_element_by_id, get_attribute_with_ns
from utils.common_utils import create_sub_element, create_element, create_comment, create_stereotypes
from utils.relationships_utils import create_relationship, resort_relationships
from utils.bdd_utils import create_class, create_instance, create_port, create_enumeration
from utils.ibd_utils import create_ibd_property, create_connector
from utils.pkg_utils import create_package
from utils.req_utils import create_requirement
from utils.act_utils import (
    create_activity, create_interruptible_region, create_node, create_action, create_edge, create_partition,
    valid_node_types, valid_action_types
)
from utils.uc_utils import create_use_case
from utils.stm_utils import create_state_machine, create_transition, create_vertex
from utils.sd_utils import create_fragment, create_lifeline, create_message, create_sd_constraint
from diagrams.md_common import add_md_owned_views

from lxml import etree
from datetime import datetime

element_configs = [
    # Common
    ("blocks", "Class", {"create_fn": create_class}),
    ("classes", "Class", {"create_fn": create_class}),
    ("packages", "Package", {"create_fn": lambda e, p: create_package(e, p.getroottree().getroot())}),
    ("interfaces", "Interface", {"create_fn": lambda e, p: create_class(e, p, xmi_type="uml:Interface")}),
    ("flowSpecifications", "Interface", {"stereotype": "FlowSpecification", "create_fn": lambda e, p: create_class(e, p, xmi_type="uml:Interface")}),
    ("signals", "Signal", {"create_fn": lambda e, p: create_class(e, p, xmi_type="uml:Signal")}),
    ("instanceSpecifications", "InstanceSpecification", {"create_fn": create_instance}),
    ("dataTypes", "DataType", {"create_fn": lambda e, p: create_class(e, p, xmi_type="uml:DataType")}),
    ("units", "InstanceSpecification", {"stereotype": "Unit", "create_fn": create_instance}),
    ("enumerations", "Enumeration", {"create_fn": create_enumeration}),
    ("activities", "Class", {"create_fn": create_activity}),
    ("stateMachines", "Class", {"create_fn": create_state_machine}),
    # REQ
    ("requirements", "Class", {"stereotype": "Requirement", "create_fn": create_requirement}),
    ("testCases", "Class", {"stereotype": "TestCase", "create_fn": create_activity}),
    # UC
    ("useCases", "UseCase", {"create_fn": create_use_case}),
    ("actors", "Actor", {"create_fn": lambda e, p: create_class(e, p, xmi_type="uml:Actor")}),
    # ACT
    ("nodes", "Node", {"create_fn": create_node}),
    ("actions", "Action", {"create_fn": create_action, "update_used_elements": True}),
    ("edges", "ControlFlow", {"create_fn": create_edge}),
    ("partitions", "SwimlaneHeader", {"create_fn": create_partition}),
    ("interruptibleRegions", "InterruptibeActivityRegion", {"create_fn": create_interruptible_region}),
    # STM
    ("connectionPoints", "State", {"create_fn": create_vertex, "update_used_elements": True}),
    ("vertices", "State", {"create_fn": create_vertex, "update_used_elements": True}),
    ("transitions", "Transition", {"create_fn": create_transition}),
    # SD
    ("lifelines", "SequenceLifeline", {"create_fn": create_lifeline}),
    ("fragments", "Fragment", {"create_fn": create_fragment, "update_used_elements": True}),
    ("messages", "SeqMessage", {"create_fn": create_message}), # Must be created after lifelines and fragments
    ("constraints", "SDConstraint", {"create_fn": create_sd_constraint}),
    # Common
    ("referencedDiagrams", "DiagramShape", {}),
]

def process_diagram(diagram, parent_elem):
    """
    Process a single diagram and generate the corresponding XMI elements.
    """
    if "id" not in diagram:
        diagram["id"] = gen_id()

    root = parent_elem.getroottree().getroot()

    used_elements = []

    # Define top-level region for State Machine Diagrams
    top_region_elem = None
    if diagram.get("diagramType") == "stm":
        top_region_elem = parent_elem.find("./region")
        if top_region_elem is None:
            top_region_elem = create_sub_element(parent_elem, "region", attrib={
                etree.QName(namespaces["xmi"], "type"): "uml:Region",
                etree.QName(namespaces["xmi"], "id"): diagram["id"] + "_region",
                "visibility": "public",
            })

    # Sort SD messages
    if diagram.get("diagramType") == "sd":
        diagram["messages"] = sorted(diagram.get("messages", []), key=lambda m: m.get("sequenceNumber", 0))
    
    # Process elements based on their type and configuration
    for key, element_class, config in element_configs:
        for element in diagram.get(key, []):
            if "stereotype" in config and config["stereotype"] not in element.get("stereotypes", []):
                element.setdefault("stereotypes", []).append(config["stereotype"])

            if key == "blocks" and "AssociationBlock" in element.get("stereotypes", []):
                element["stereotypes"].remove("AssociationBlock")
            elif ((key == "nodes" and element.get("nodeType") not in valid_node_types)
                or (key == "actions" and element.get("type") not in valid_action_types)):
                continue
            else:
                used_elements.append({"element": element, "element_class": element_class})

            if "originalID" in element and "id" not in element:
                element["id"] = element["originalID"]
                continue

            if "create_fn" in config:
                args = []
                if config.get("update_used_elements") == True:
                    args.append(used_elements)
                parent = top_region_elem if key in ("vertices", "transitions") and top_region_elem is not None else parent_elem
                config["create_fn"](element, parent, *args)

    ### IBD elements
    ports_lookup = {port.get("id"): port for port in diagram.get("ports", []) if "id" in port}
    properties_lookup = {prop.get("id"): prop for prop in diagram.get("properties", []) if "id" in prop}

    for property in diagram.get("properties", []):
        create_ibd_property(property, parent_elem, used_elements, ports_lookup)

    if diagram.get("context", {}).get("ports", []):
        for port_idref in diagram["context"]["ports"]:
            port = ports_lookup.get(port_idref)
            if port:
                create_port(port, parent_elem)
                used_elements.append(
                    {"element": {**port, "portOwnerIdref": diagram.get("id")},
                    "element_class": "Port"}
                )

    for connector in diagram.get("connectors", []):
        if "id" not in connector:
            connector["id"] = gen_id()
        for end in connector.get("ends", []):
            if "idref" in end and end["idref"] in properties_lookup:
                end["type"] = properties_lookup[end["idref"]].get("type")
        relationship_result = create_connector(connector, parent_elem, diagram.get("properties", []))
        if relationship_result and "member_end_ids" in relationship_result and len(relationship_result["member_end_ids"]) == 2:
            connector["member_end_ids"] = relationship_result["member_end_ids"]     
        used_elements.append({"element": connector, "element_class": "Connector"})

    ### Relationships
    diagram = resort_relationships(diagram)

    for relationship in diagram.get("relationships", []):
        if "id" not in relationship:
            relationship["id"] = gen_id()
        element_class = "Association"
        relationship_type = relationship.get("type")
        if relationship_type == "AssociationClass":
            element_class = "AssociationClass"
            if "AssociationBlock" in relationship.get("stereotypes", []):
                relationship["stereotypes"].remove("AssociationBlock")
        elif relationship_type == "Containment":
            element_class = "ContainmentLink"
        elif relationship_type in ["Abstraction", "Dependency"]:
            element_class = "Dependency"
        elif relationship_type in ["Generalization", "PackageImport", "Extend", "Include"]:
            element_class = relationship_type

        relationship_result = create_relationship(relationship, parent_elem)
        if relationship_result and  "member_end_ids" in relationship_result and len(relationship_result["member_end_ids"]) == 2:
            relationship["member_end_ids"] = relationship_result["member_end_ids"]

        used_elements.append({"element": relationship, "element_class": element_class})

    ### Comments
    for comment in diagram.get("comments", []):
        if "id" not in comment:
            comment["id"] = gen_id()
        used_elements.append({"element": comment, "element_class": "Comment"})
        comment_result = create_comment(comment, parent_elem)
        if comment_result and "annotated_element_ids" in comment_result:
            comment["annotated_element_ids"] = comment_result["annotated_element_ids"]

    # Handle System Boundary for Use Case Diagrams
    if "systemBoundary" in diagram:
        system_boundary = diagram["systemBoundary"]
        if "idref" not in system_boundary:
            system_boundary["idref"] = gen_id()
        boundary_stereotypes = system_boundary.get("stereotypes", [])
        if boundary_stereotypes == [] or "useCaseModel" in boundary_stereotypes:
            used_elements.append({"element": system_boundary, "element_class": "Package"})
            use_case_model = create_package({
                "id": system_boundary["idref"],
                "name": system_boundary.get("name", "System Boundary"),
                "owner": diagram.get("owner", {}),
                "stereotypes": boundary_stereotypes
            }, root)

            for uc_id in system_boundary.get("ownedUseCases", []):
                uc_elem = find_element_by_id(uc_id, parent_elem)
                if uc_elem is not None:
                    use_case_model.append(uc_elem)
        else:
            block_used_element = next(
                (
                    elem for elem in used_elements
                    if elem.get("element", {}).get("id") == system_boundary["idref"]
                ), None
            )
            if block_used_element is None:
                used_elements.append({"element": system_boundary, "element_class": "Class"})
            else:
                block_used_element["element"]["ownedUseCases"] = system_boundary.get("ownedUseCases", [])
            block_elem = create_class({
                "id": system_boundary["idref"],
                "name": system_boundary.get("name", "System Boundary"),
                "stereotypes": boundary_stereotypes
            }, parent_elem)

            for uc_id in system_boundary.get("ownedUseCases", []):
                uc_elem = find_element_by_id(uc_id, parent_elem)
                if uc_elem is not None:
                    if uc_id not in [
                        get_attribute_with_ns("idref", uc_ref)
                        for uc_ref in block_elem.findall("useCase")
                    ]:
                        create_sub_element(block_elem, "useCase", attrib={
                            etree.QName(namespaces["xmi"], "idref"): uc_id
                        })
                    if system_boundary["idref"] not in [
                        get_attribute_with_ns("idref", subject)
                        for subject in uc_elem.findall("subject")
                    ]:
                        create_sub_element(uc_elem, "subject", attrib={
                            etree.QName(namespaces["xmi"], "idref"): system_boundary["idref"]
                        })

    # Add Diagram Extension
    diagram_ext = add_diagram_extension(diagram, parent_elem, used_elements)
    # Add Diagram Stereotypes
    stereotypes = diagram.get("stereotypes", [])
    if "DiagramInfo" not in stereotypes:
        stereotypes.append("DiagramInfo")
    if diagram.get("partitions"):
        stereotypes.insert(0, "SwimLaneDiagram")
    tagged_values = {
        "Creation_date": datetime.now().strftime("%m/%d/%y, %I:%M %p"),
        "Modification_date": datetime.now().strftime("%m/%d/%y, %I:%M %p"),
        "Author": "JsonSysML-to-XMI Converter",
        "Last_modified_by": "JsonSysML-to-XMI Converter",
    }
    create_stereotypes(diagram.get("id"), stereotypes, root, tagged_values)
    # Add mdOwnedViews
    add_md_owned_views(
        diagram,
        diagram_ext.get("stream_content_id"),
        used_elements,
        root
    )

def add_diagram_extension(diagram, parent_elem, used_elements):
    """
    Adds the MagicDraw-specific diagram extension to the XMI representation of the diagram.
    """
    diagram_nsmap = {
        "binary": "http://www.nomagic.com/ns/cameo/client/binary/1.0",
        "diagram": "http://www.nomagic.com/ns/magicdraw/core/diagram/1.0",
        "xmi": "http://www.omg.org/XMI",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    }

    xmi_ext = create_element(
        etree.QName(namespaces["xmi"], "Extension"),
        attrib={"extender": "MagicDraw UML 2024x"}
    )
    parent_elem.insert(0, xmi_ext)

    model_ext = create_sub_element(xmi_ext, "modelExtension")

    owned_diag = create_sub_element(
        model_ext,
        "ownedDiagram",
        attrib={
            etree.QName(namespaces["xmi"], "type"): "uml:Diagram",
            etree.QName(namespaces["xmi"], "id"): diagram.get("id"),
            "name": diagram.get("name", "Unnamed Diagram"),
            "visibility": "public",
            "ownerOfDiagram": get_attribute_with_ns("id", parent_elem),
        }
    )

    if diagram.get("context", {}).get("idref"):
        owned_diag.set("context", diagram.get("context", {}).get("idref"))

    inner_xmi_ext = create_sub_element(
        owned_diag,
        etree.QName(namespaces["xmi"], "Extension"),
        attrib={"extender": "MagicDraw UML 2024x"}
    )

    diagram_rep = create_sub_element(inner_xmi_ext, "diagramRepresentation")

    diagram_type = diagram.get("diagramType", "bdd")
    diag_obj = create_sub_element(
        diagram_rep,
        etree.QName(diagram_nsmap["diagram"], "DiagramRepresentationObject"),
        attrib={
            "ID": gen_id(),
            "initialFrameSizeSet": "true",
            "requiredFeature": get_diagram_required_features(diagram_type),
            "type": diagram_full_types.get(diagram_type),
            "umlType": diagram_uml_types.get(diagram_type),
            etree.QName(diagram_nsmap["xmi"], "id"): gen_id(),
            etree.QName(diagram_nsmap["xmi"], "version"): "2.0",
        },
        nsmap=diagram_nsmap
    )

    diagram_contents = create_sub_element(
        diag_obj,
        "diagramContents",
        attrib={
            "contentHash": gen_id(),
            "exporterName": "MagicDraw UML",
            "exporterVersion": "2024x v6",
            etree.QName(diagram_nsmap["xmi"], "id"): gen_id(),
        }
    )

    stream_content_id = "BINARY-" + gen_id()[1:]
    create_sub_element(
        diagram_contents,
        "binaryObject",
        attrib={
            "streamContentID": stream_content_id,
            etree.QName(diagram_nsmap["xmi"], "id"): gen_id(),
            etree.QName(diagram_nsmap["xsi"], "type"): "binary:StreamIdentityBinaryObject",
        }
    )

    # Used Objects
    for item in used_elements:
        idref = item.get("element", {}).get("id") or item.get("element", {}).get("idref")
        if idref is not None:
            create_sub_element(diagram_contents, "usedObjects", attrib={"href": f"#{idref}"})

    # Used Elements
    for item in used_elements:
        idref = item.get("element", {}).get("id") or item.get("element", {}).get("idref")
        if idref is not None:
            el = create_sub_element(diagram_contents, "usedElements")
            el.text = idref

    return {
        "stream_content_id": stream_content_id,
    }