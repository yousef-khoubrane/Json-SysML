
from utils.helpers import namespaces, gen_id, smart_uncast, predefined_types, get_predefined_type_info
from utils.getter_utils import (
    find_element_by_id,
    find_root_model,
    get_closest_package,
    get_attribute_with_ns
)
import utils.variables as VARIABLES

from lxml import etree

def create_sub_element(*args, **kwargs):
    element = etree.SubElement(*args, **kwargs)
    id = get_attribute_with_ns("id", element)
    if id:
        VARIABLES.CREATED_NODES[id] = element
    return element

def create_element(*args, **kwargs):
    element = etree.Element(*args, **kwargs)
    id = get_attribute_with_ns("id", element)
    if id:
        VARIABLES.CREATED_NODES[id] = element
    return element

def update_created_nodes(remove=[], add={}):
    for id in remove:
        if id in VARIABLES.CREATED_NODES:
            del VARIABLES.CREATED_NODES[id]
    for id, node in add.items():
        VARIABLES.CREATED_NODES[id] = node

def replace_model_id(model, new_id):
    old_id = model.get("id", "model")
    if old_id != new_id:
        model["id"] = new_id
    
    for diagram in model.get("diagrams", []):
        owner_id_path = diagram.get("owner", {}).get("idPath", "")
        if owner_id_path.startswith(old_id):
            diagram["owner"]["idPath"] = new_id + owner_id_path[len(old_id):]
        for package in diagram.get("packages", []):
            package_owner_id_path = package.get("owner", {}).get("idPath", "")
            if package_owner_id_path.startswith(old_id):
                package["owner"]["idPath"] = new_id + package_owner_id_path[len(old_id):]

    # Recursively replace ids and idrefs in the entire model
    def recursive_replace(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in ["id", "idref"] and value == old_id:
                    obj[key] = new_id
                else:
                    recursive_replace(value)
        elif isinstance(obj, list):
            for idx in range(len(obj)):
                if isinstance(obj[idx], str) and obj[idx] == old_id:
                    obj[idx] = new_id
                else:
                    recursive_replace(obj[idx])

    recursive_replace(model)

    return model

def sort_diagrams(model):
    """
    Sorts diagrams first by their type (according to a custom order)
    and then alphabetically by name within each type.
    """
    # Define the custom order of diagram types
    type_order = ["bdd", "req", "pkg", "uc", "ibd", "par", "act", "sd", "stm"]
    
    # Create a mapping of type to its index (priority)
    # Default to a high number if the type isn't in our list
    order_map = {t: i for i, t in enumerate(type_order)}

    diagrams = model.get("diagrams", [])

    if diagrams:
        # Sort using a tuple key: (Type Priority, Name)
        diagrams.sort(key=lambda d: (
            order_map.get(d.get("diagramType", ""), 999), 
            d.get("name", "").lower()
        ))
        
        model["diagrams"] = diagrams
        
    return model

full_form = {
    ** {
        stereo: etree.QName(namespaces["sysml"], stereo)
        for stereo in [
            "Block", "Requirement", "FlowProperty", "ConnectorProperty", "DirectedFeature", "FlowPort",
            "ProxyPort", "FullPort", "Uniform", "BindingConnector", "NestedConnectorEnd",
            "ConstraintBlock", "System", "Domain", "External", "Rationale", "FlowSpecification",
            "ParticipantProperty", "Conform", "moe", "View", "Viewpoint", "Expose", "Problem",
            "DeriveReqt", "Satisfy", "Verify", "Refine", "Copy", "Trace", "TestCase", "ValueType",
            "objectiveFunction", "ItemFlow", "Continuous", "AllocateActivityPartition", "Allocate",
            "SwimLaneDiagram", "InterfaceBlock", "_InterfaceBlock", "physicalRequirement",
            "functionalRequirement", "interfaceRequirement", "performanceRequirement",
            "extendedRequirement", "Subsystem", "System_context",
        ]
    },
    ** {
        stereo: etree.QName(namespaces["MD_Customization_for_SysML__additional_stereotypes"], stereo)
        for stereo in [
            "PartProperty", "ValueProperty", "ConstraintProperty", "ReferenceProperty",
            "SharedProperty", "ConstraintParameter", "Unit", "QuantityKind",
        ]
    },
    ** {
        stereo: etree.QName(namespaces["StandardProfile"], stereo)
        for stereo in [
            "ModelLibrary"
        ]
    },
    ** {
        stereo: etree.QName(namespaces["MagicDraw_Profile"], stereo)
        for stereo in [
            "DiagramInfo", "useCaseModel", "Legend", "AttachedFile"
        ]
    },
}

base_element = {
    "DirectedFeature": "base_Feature",
    "FlowSpecification": "base_Interface",
    "Conform": "base_Generalization",
    "ModelLibrary": "base_Package",
    "useCaseModel": "base_Model",
    "TestCase": "base_Behavior",
    "ValueType": "base_DataType",
    "BindingConnector": "base_Connector",
    "NestedConnectorEnd": "base_ConnectorEnd",
    "ItemFlow": "base_InformationFlow",
    "Continuous": "base_ObjectNode",
    "AllocateActivityPartition": "base_ActivityPartition",
    ** {
        stereo: "base_Class"
        for stereo in [
            "Block", "Requirement", "ConstraintBlock", "System", "Domain", "External",
            "View", "Viewpoint", "InterfaceBlock", "_InterfaceBlock", "physicalRequirement",
            "functionalRequirement", "interfaceRequirement", "performanceRequirement",
            "extendedRequirement", "Legend", "Subsystem", "System_context"
        ]
    },
    ** {
        stereo: "base_Property"
        for stereo in [
            "PartProperty", "FlowProperty", "ConnectorProperty", "ValueProperty",
            "ConstraintProperty", "ReferenceProperty", "SharedProperty",
            "ParticipantProperty", "Uniform", "moe", "objectiveFunction"
        ]
    },
    ** {
        stereo: "base_Port"
        for stereo in [
            "FlowPort", "ProxyPort", "FullPort", "ConstraintParameter"
        ]
    },
    ** {
        stereo: "base_Diagram"
        for stereo in [
            "DiagramInfo", "SwimLaneDiagram"
        ]
    },
    ** {
        stereo: "base_Dependency"
        for stereo in [
            "Expose"
        ]
    },
    ** {
        stereo: "base_Abstraction"
        for stereo in [
            "DeriveReqt", "Satisfy", "Verify", "Refine", "Copy", "Trace", "Allocate"
        ]
    },
    ** {
        stereo: "base_InstanceSpecification"
        for stereo in [
            "Unit", "QuantityKind"
        ]
    },
    ** {
        stereo: "base_Comment"
        for stereo in [
            "Rationale", "Problem", "AttachedFile"
        ]
    }
}

def create_stereotypes(element_id, stereotypes, root, tagged_values={}):
    if not stereotypes or element_id is None:
        return None

    stereo_element = None
    for stereo in stereotypes:
        try:
            app_id = gen_id()
            # check if stereotype already exists for this element
            expected_tag = f"{{{full_form[stereo].namespace}}}{full_form[stereo].localname}"
            stereo_element = None
            for existing in root.findall("./" + expected_tag):
                if existing.get(base_element[stereo]) == element_id:
                    stereo_element = existing
                    break

            if stereo_element is None:
                stereo_element = create_sub_element(root, full_form[stereo], attrib={
                    etree.QName(namespaces["xmi"], "id"): app_id,
                    base_element[stereo]: element_id
                })
        except KeyError:
            VARIABLES.UNRECOGNIZED_STEREOTYPES.add(stereo)

    if tagged_values and stereo_element is not None:
        for tag, value in tagged_values.items():
            if smart_uncast(value):
                stereo_element.set(tag, smart_uncast(value))

    return stereo_element

def remove_stereotypes(element_id, stereotypes, root):
    if not stereotypes or element_id is None:
        return None

    for stereo in stereotypes:
        try:
            expected_tag = f"{{{full_form[stereo].namespace}}}{full_form[stereo].localname}"
            for existing in root.findall("./" + expected_tag):
                if existing.get(base_element[stereo]) == element_id:
                    root.remove(existing)
                    break
        except KeyError:
            continue

def create_type(type, parent_elem, parent_stereotypes=[]):
    if type is None or parent_elem is None:
        return None
    type_elem = None
    if not isinstance(type, dict):
        return None
    type_ref = type.get("idref")
    if type_ref:
        root = parent_elem.getroottree().getroot()
        model_elem = find_root_model(root)
        parent_elem.set("type", type_ref)
        type_elem = find_element_by_id(type_ref, parent_elem, top_node=model_elem)
        if type_elem is None:
            type_elem = create_sub_element(get_closest_package(parent_elem), "packagedElement", attrib={
                etree.QName(namespaces["xmi"], "type"): "uml:Class",
                etree.QName(namespaces["xmi"], "id"): type_ref,
                "name": type.get("name", "")
            })
        if "ValueProperty" in parent_stereotypes:
            type_elem.set(etree.QName(namespaces["xmi"], "type"), "uml:DataType")
            create_stereotypes(type_ref, ["ValueType"], root)

        if type.get("unit", {}).get("idref") and get_attribute_with_ns("type", type_elem) == "uml:DataType":
            unit_ref = type["unit"]["idref"]
            unit_elem = find_element_by_id(unit_ref, parent_elem, top_node=model_elem)
            if unit_elem is None:
                unit_elem = create_sub_element(get_closest_package(parent_elem), "packagedElement", attrib={
                    etree.QName(namespaces["xmi"], "type"): "uml:InstanceSpecification",
                    etree.QName(namespaces["xmi"], "id"): unit_ref,
                    "name": type["unit"].get("name", "")
                })
                create_stereotypes(unit_ref, ["Unit"], root)
            create_stereotypes(type_ref, ["ValueType"], root, tagged_values={
                "unit": unit_ref
            })

    elif type.get("name") in predefined_types:
        type_elem = create_predefined_type(type.get("name"), parent_elem)

    if type_elem is not None:
        if type.get("generalization") in predefined_types:
            existing_generalization = type_elem.find("generalization")
            if existing_generalization is None:
                generalization_elem = create_sub_element(type_elem, "generalization", attrib={
                    etree.QName(namespaces["xmi"], "type"): "uml:Generalization",
                    etree.QName(namespaces["xmi"], "id"): gen_id()
                })
                general = create_predefined_type(type.get("generalization"), generalization_elem)
                if general is not None:
                    general.tag = "general"

    return type_elem

def create_predefined_type(type, parent_elem):
    if type not in predefined_types:
        return None
    existing = parent_elem.find("type")
    if existing is not None:
        return existing
    type_elem = create_element("type", attrib={"href": get_predefined_type_info(type).get("href", "")})
    xmi_ext = create_sub_element(
        type_elem,
        etree.QName(namespaces["xmi"], "Extension"),
        attrib={"extender": "MagicDraw UML 2024x"}
    )
    create_sub_element(
        xmi_ext, "referenceExtension",
        attrib=get_predefined_type_info(type).get("referenceExtension_attributes", {})
    )
    if type == "VerdictKind" and not parent_elem.getparent().xpath("./node[@type='uml:ActivityParameterNode']"):
        node = create_sub_element(parent_elem.getparent(), "node", attrib={
            etree.QName(namespaces["xmi"], "type"): "uml:ActivityParameterNode",
            etree.QName(namespaces["xmi"], "id"): f"{get_attribute_with_ns('id', parent_elem)}_node",
            "name": "verdict",
            "visibility": "public",
            "parameter": get_attribute_with_ns("id", parent_elem)
        })
        node.append(etree.fromstring(etree.tostring(type_elem)))
    if type_elem is not None and not parent_elem.xpath("./type"):
        parent_elem.append(type_elem)
    return type_elem

def create_multiplicity(mult, parent_elem):
    if mult == None:
        return
    if parent_elem.xpath("./lowerValue") or parent_elem.xpath("./upperValue"):
        return
    mult = str(mult)
    lower, upper = "1", "1"
    if ".." in mult:
        lower, upper = mult.split("..")
    else:
        lower = upper = mult
    lower_value_uml_type = "uml:LiteralUnlimitedNatural" if lower == "*" else "uml:LiteralInteger"
    create_sub_element(parent_elem, "lowerValue", attrib={
        etree.QName(namespaces["xmi"], "type"): lower_value_uml_type,
        etree.QName(namespaces["xmi"], "id"): gen_id(),
        "value": lower
    })
    create_sub_element(parent_elem, "upperValue", attrib={
        etree.QName(namespaces["xmi"], "type"): "uml:LiteralUnlimitedNatural",
        etree.QName(namespaces["xmi"], "id"): gen_id(),
        "value": upper
    })

def create_boolean_values(element_dict, parent_elem):
    is_bool = lambda k: k.startswith("is") and k[2].isupper() and isinstance(element_dict[k], bool)
    for key in element_dict.keys():
        if is_bool(key):
            parent_elem.set(key, str(element_dict[key]).lower())

def create_comment(comment, parent_elem):
    if comment.get("stereotypes") in [["Previous"], ["Next"]]:
        return {} # Skip Previous and Next comments
    if "id" not in comment:
        comment["id"] = gen_id()
    comment_id = comment["id"]
    comment_elem = find_element_by_id(comment_id, parent_elem)
    if comment_elem is not None:
        return {} # Comment already exists
    comment_elem = create_sub_element(parent_elem, "ownedComment", attrib={
        etree.QName(namespaces["xmi"], "type"): "uml:Comment",
        etree.QName(namespaces["xmi"], "id"): comment_id,
    })
    body_text = comment.get("body", "")
    if body_text:
        comment_elem.set("body", body_text)
    for annotated_elem_id in comment.get("annotatedElements", []):
        create_sub_element(comment_elem, "annotatedElement", attrib={
            etree.QName(namespaces["xmi"], "idref"): annotated_elem_id
        })
    create_boolean_values(comment, comment_elem)
    create_stereotypes(
        comment_id,
        comment.get("stereotypes", []),
        parent_elem.getroottree().getroot(),
        comment.get("taggedValues", {})
    )
    return {"annotated_element_ids": comment.get("annotatedElements", [])}