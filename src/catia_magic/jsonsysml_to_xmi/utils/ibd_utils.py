
from utils.helpers import namespaces, gen_id
from utils.getter_utils import (
    find_element_by_id,
    find_root_model,
    get_attribute_with_ns,
    get_closest_package,
    get_element_stereotypes,
)
from utils.common_utils import (
    create_sub_element,
    create_boolean_values,
    create_multiplicity,
    create_stereotypes,
)
from utils.bdd_utils import create_class, create_constraint, create_port, create_property

from lxml import etree

def create_ibd_property(property, parent_elem, diagram_used_elements = [], ports_lookup = {}):

    if "id" not in property:
        property["id"] = gen_id()

    root = parent_elem.getroottree().getroot()
    model_elem = find_root_model(root)
    package_elem = get_closest_package(parent_elem)

    prop_elem = create_property(property, parent_elem, find_root_model(root))
    diagram_used_elements.append({"element": property, "element_class": "Part"})

    for i, prop in enumerate(property.get("shortcutPath", [])):
        prop_parent = parent_elem
        if i > 0:
            candidate_parent = find_element_by_id(
                property.get("shortcutPath")[i-1].get("type", {}).get("idref"),
                parent_elem, top_node=model_elem
            )
            if candidate_parent is not None:
                prop_parent = candidate_parent
        create_property({"id": prop.get("idref"), **prop}, prop_parent, model_elem)

    if not property.get("type", {}).get("idref"):
        return
    
    property_type_element = find_element_by_id(property.get("type").get("idref"), parent_elem, top_node=model_elem)
    if property_type_element is None:
        property_type_element = create_class(
            {
                "id": property.get("type").get("idref"),
                "name": property.get("type").get("name", "")
            },
            package_elem
        )
    if "ConstraintProperty" in property.get("stereotypes", []):
        create_stereotypes(property.get("type").get("idref"), ["ConstraintBlock"], root)
    for constraint in property.get("constraints", []):
        create_constraint(constraint, property_type_element)

    for port_idref in property.get("ports", []):
        port = ports_lookup.get(port_idref)
        if port:
            create_port(port, property_type_element)
            diagram_used_elements.append(
                {"element": {**port, "portOwnerIdref": property.get("id")},
                 "element_class": "Port"}
            )

    for nested_prop in property.get("nestedProperties", []):
        create_ibd_property(nested_prop, property_type_element, diagram_used_elements, ports_lookup)

def create_connector(connector, parent_elem, diagram_properties):

    ends_idrefs = [end.get("idref") for end in connector.get("ends", []) if end.get("idref")]
    if len(ends_idrefs) != 2:
        return

    root = parent_elem.getroottree().getroot()
    model_elem = find_root_model(root)
    if "id" not in connector:
        connector["id"] = gen_id()

    connector_elem = find_element_by_id(connector.get("id"), parent_elem)
    if connector_elem is not None:
        return  {
            "member_end_ids": [
                get_attribute_with_ns("id", end)
                for end in connector_elem.findall("end")
            ]
        }

    connector_elem = create_sub_element(parent_elem, "ownedConnector", attrib={
        etree.QName(namespaces["xmi"], "type"): "uml:Connector",
        etree.QName(namespaces["xmi"], "id"): connector.get("id"),
        "name": connector.get("name", ""),
        "visibility": "public"
    })

    properties_lookup = {prop.get("id"): prop for prop in diagram_properties if "id" in prop}
    member_end_ids = []
    end_owner_idrefs = []
    end_ids = {}
    for end in connector.get("ends"):
        end_id = gen_id()
        end_ids[end.get("idref")] = end_id
        end_elem = create_sub_element(connector_elem, "end", attrib={
            etree.QName(namespaces["xmi"], "type"): "uml:ConnectorEnd",
            etree.QName(namespaces["xmi"], "id"): end_id,
            "role": end.get("idref"),
        })
        tagged_values = {}
        end_owner_idref = end.get("idref")
        if properties_lookup.get(end.get("idref"), {}).get("shortcutPath"):
            nested_props = " ".join([prop["idref"] for prop in properties_lookup.get(end.get("idref")).get("shortcutPath") if "idref" in prop])
            tagged_values["propertyPath"] = nested_props
        if end.get("portOwnerIdref"):
            end_elem.set("partWithPort", end.get("portOwnerIdref"))
            tagged_values["propertyPath"] = f"{tagged_values.get('propertyPath', '')} {end.get('portOwnerIdref')}".strip()
            end_owner_idref = end.get("portOwnerIdref")
        create_multiplicity(end.get("multiplicity"), end_elem)
        create_stereotypes(end_id, ["NestedConnectorEnd"], root, tagged_values=tagged_values)
        member_end_ids.append(end_id)
        end_owner_idrefs.append(end_owner_idref)

    # Find LCA of the two ends and attach the connector to it
    property_parent_lookup = build_property_parent_lookup(diagram_properties)
    lca_idref, is_immediate = get_lca(*end_owner_idrefs, property_parent_lookup)
    if lca_idref:
        lca_element = find_element_by_id(lca_idref, parent_elem, top_node=model_elem)
        if lca_element is not None and lca_element.get("type"):
            property_owner_elem = find_element_by_id(lca_element.get("type"), parent_elem, top_node=model_elem)
            if property_owner_elem is not None:
                property_owner_elem.append(connector_elem)

    if not is_immediate and ends_idrefs == end_owner_idrefs: # The ends are not ports
        for end_idref in ends_idrefs:
            parent = property_parent_lookup.get(end_idref)
            parent_before = ""
            property_path = ""
            if parent:
                while parent != lca_idref and parent is not None:
                    property_path = f"{parent} {property_path}"
                    parent_before = parent
                    parent = property_parent_lookup.get(parent)
                parent = parent_before
                nested_props = ""
                if properties_lookup.get(parent, {}).get("shortcutPath"):
                    nested_props = " ".join([
                        prop["idref"] for prop in properties_lookup.get(parent).get("shortcutPath")
                        if "idref" in prop
                    ])
                property_path = f"{nested_props.strip()} {property_path.strip()}"
                end_id = end_ids[end_idref]
                tagged_values = {"propertyPath": property_path.strip()}
                create_stereotypes(end_id, ["NestedConnectorEnd"], root, tagged_values=tagged_values)

    for item_flow in connector.get("itemFlows", []):
        create_item_flow(item_flow, connector_elem)

    create_boolean_values(connector, connector_elem)
    create_stereotypes(
        connector.get("id"),
        connector.get("stereotypes", []),
        root,
        tagged_values=connector.get("taggedValues", {})
    )

    return {
        "member_end_ids": member_end_ids
    }

def create_item_flow(item_flow, connector_elem):

    if "id" not in item_flow:
        item_flow["id"] = gen_id()
    
    root = connector_elem.getroottree().getroot()
    model_elem = find_root_model(root)
    item_flow_elem = find_element_by_id(item_flow.get("id"), connector_elem.getparent(), top_node=model_elem)
    if item_flow_elem is not None:
        return
    
    connector_id = get_attribute_with_ns("id", connector_elem)
    parent_pkg = get_closest_package(connector_elem)

    item_flow_elem = create_sub_element(parent_pkg, "packagedElement", attrib={
        etree.QName(namespaces["xmi"], "type"): "uml:InformationFlow",
        etree.QName(namespaces["xmi"], "id"): item_flow.get("id"),
        "name": item_flow.get("name", "")
    })

    conveyed_idref = item_flow.get("conveyed", {}).get("idref")
    if conveyed_idref:
        create_sub_element(item_flow_elem, "conveyed", attrib={
            etree.QName(namespaces["xmi"], "idref"): conveyed_idref
        })
        conveyed_elem = find_element_by_id(conveyed_idref, connector_elem.getparent(), top_node=model_elem)
        if conveyed_elem is None:
            conveyed_elem = create_class(
                {
                    "id": conveyed_idref,
                    "name": item_flow.get("conveyed").get("name", ""),
                    "stereotypes": ["Block"]
                },
                parent_pkg
            )

    ends = {
        "sourceIdref": "informationSource",
        "targetIdref": "informationTarget"
    }
    roles = [end.get("role") for end in connector_elem.findall("end")]
    for key, tag in ends.items():
        if item_flow.get(key):
            idref = item_flow.get(key)
            create_sub_element(item_flow_elem, tag, attrib={
                etree.QName(namespaces["xmi"], "idref"): idref
            })
            if idref not in roles:
                stereotypes = get_element_stereotypes(find_element_by_id(
                    idref, connector_elem.getparent(), top_node=model_elem
                ))
                if all(item not in stereotypes for item in [
                    "Block", "System", "Domain", "External", "Subsystem", "System_context"
                ]):
                    create_stereotypes(idref, ["Block"], root)
    create_sub_element(item_flow_elem, "realizingConnector", attrib={
        etree.QName(namespaces["xmi"], "idref"): connector_id
    })
    
    tagged_values = {}
    item_property_idref = item_flow.get("itemProperty", {}).get("idref")
    if item_property_idref:
        tagged_values["itemProperty"] = item_property_idref
        item_property_elem = find_element_by_id(item_property_idref, connector_elem.getparent())
        if item_property_elem is None:
            item_property_elem = create_sub_element(connector_elem.getparent(), "ownedAttribute", attrib={
                etree.QName(namespaces["xmi"], "type"): "uml:Property",
                etree.QName(namespaces["xmi"], "id"): item_property_idref,
                "name": item_flow.get("itemProperty", {}).get("name", ""),
                "visibility": "public",
                "aggregation": "composite"
            })
            if conveyed_idref:
                item_property_elem.set("type", conveyed_idref)
            create_stereotypes(item_property_idref, ["PartProperty"], root)

    create_boolean_values(item_flow, item_flow_elem)
    create_stereotypes(item_flow.get("id"), ["ItemFlow"], root, tagged_values)

def build_property_parent_lookup(properties, parent_id=None):
    lookup = {}
    for prop in properties:
        prop_id = prop.get("id")
        if not prop_id:
            continue
            
        # Assign the parent_id to the current property
        lookup[prop_id] = parent_id
        
        # If there are nested properties, recurse deeper
        if "nestedProperties" in prop:
            # The current prop_id becomes the parent for the next level
            child_lookup = build_property_parent_lookup(
                prop["nestedProperties"], 
                parent_id=prop_id
            )
            lookup.update(child_lookup)
        # Also consider ports as potential parents if they are associated with this property
        for port_idref in prop.get("ports", []):
            lookup[port_idref] = prop_id
            
    return lookup

def get_lca(id1, id2, parent_lookup):
    """Get the Lowest Common Ancestor (LCA) of two elements given their IDs and a parent lookup."""
    # 1. Build the path from id1 up to the root
    path1 = []
    curr = id1
    while curr is not None:
        path1.append(curr)
        curr = parent_lookup.get(curr)
    
    path1_set = set(path1)
    
    # 2. Find the LCA
    lca = None
    curr = id2
    while curr is not None:
        if curr in path1_set:
            lca = curr
            break
        curr = parent_lookup.get(curr)
        
    if lca is None:
        return None, False

    # 3. Check if LCA is the direct parent of BOTH
    is_immediate = (parent_lookup.get(id1) == lca and 
                    parent_lookup.get(id2) == lca)

    return lca, is_immediate