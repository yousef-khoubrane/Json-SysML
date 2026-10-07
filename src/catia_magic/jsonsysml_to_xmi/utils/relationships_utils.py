
from utils.helpers import namespaces, gen_id
from utils.getter_utils import (
    find_element_by_id,
    find_root_model,
    get_attribute_with_ns,
)
from utils.common_utils import (
    create_sub_element,
    create_multiplicity,
    create_stereotypes,
)
from utils.bdd_utils import create_class

from lxml import etree

def create_relationship(relationship, parent_elem):

    relationship_type = relationship.get("type")
    source_id, target_id = (
        relationship.get(key, {}).get("idref", relationship.get(key, {}).get("originalID"))
        for key in ["source", "target"]
    )
    if any(item is None for item in [relationship_type, parent_elem, source_id, target_id]):
        return {}
    
    relationship_id = relationship.get("id", gen_id())
    root = parent_elem.getroottree().getroot()
    model_elem = find_root_model(root)

    source_elem = find_element_by_id(source_id, parent_elem, top_node=model_elem)
    target_elem = find_element_by_id(target_id, parent_elem, top_node=model_elem)
    
    if relationship_type == "PackageImport":
        package_import_elem = find_element_by_id(relationship_id, source_elem)
        if package_import_elem is None:
            package_import_elem = create_sub_element(source_elem, "packageImport", attrib={
                etree.QName(namespaces["xmi"], "type"): "uml:PackageImport",
                etree.QName(namespaces["xmi"], "id"): relationship_id,
                "name": relationship.get("name", "")
            })
            if "originalID" in relationship.get("target", {}):
                imported_package_elem = create_sub_element(package_import_elem, "importedPackage", attrib={
                    "href": "",
                })
                xmi_ext = create_sub_element(imported_package_elem, etree.QName(namespaces["xmi"], "Extension"), attrib={
                    "extender": "MagicDraw UML 2024x",
                })
                create_sub_element(xmi_ext, "referenceExtension", attrib={
                    "referentPath": relationship.get("target", {}).get("name", ""),
                    "referentType": "Package",
                    "originalID": target_id
                })
                return {"imported_package": imported_package_elem}
            else:
                package_import_elem.set("importedPackage", target_id)
                return {}

    if source_elem is None or target_elem is None:
        return {}
    
    create_stereotypes(relationship_id, relationship.get("stereotypes", []), root)

    if relationship_type == "Generalization":
        generalization_elem = find_element_by_id(relationship_id, source_elem)
        if generalization_elem is None and source_elem.find("generalization") is None:
            existing = source_elem.find("generalization")
            if existing is None:
                generalization_elem = create_sub_element(source_elem, "generalization", attrib={
                    etree.QName(namespaces["xmi"], "type"): "uml:Generalization",
                    etree.QName(namespaces["xmi"], "id"): relationship_id,
                    "general": target_id
                })
        return {}
    
    elif relationship_type == "Association" and (
        get_attribute_with_ns("type", source_elem) == "uml:UseCase"
        or get_attribute_with_ns("type", target_elem) == "uml:UseCase"
        ):
        assoc_elem = find_element_by_id(relationship_id, parent_elem, top_node=model_elem)
        if assoc_elem is not None:
            return  {
                "member_end_ids": [
                    get_attribute_with_ns("idref", end)
                    for end in assoc_elem.findall("memberEnd")
                ]
            }
        assoc_attrib = {
            etree.QName(namespaces["xmi"], "type"): "uml:Association",
            etree.QName(namespaces["xmi"], "id"): relationship_id,
            "name": relationship.get("name", "")
        }
        assoc_elem = create_sub_element(parent_elem, "packagedElement", attrib=assoc_attrib)

        member_end_ids = []
        for owned_end_idref in [source_id, target_id]:
            owned_end_id = gen_id()
            owned_end_attrib = {
                etree.QName(namespaces["xmi"], "type"): "uml:Property",
                etree.QName(namespaces["xmi"], "id"): owned_end_id,
                "visibility": "private",
                "type": owned_end_idref,
                "association": relationship_id
            }
            owned_end_elem = create_sub_element(assoc_elem, "ownedEnd", attrib=owned_end_attrib)
            create_multiplicity(
                relationship.get(
                    "source" if owned_end_idref == source_id else "target", {}
                ).get("multiplicity", None),
                owned_end_elem
            )
            create_sub_element(assoc_elem, "memberEnd", attrib={
                etree.QName(namespaces["xmi"], "idref"): owned_end_id,
            })
            create_sub_element(assoc_elem, "navigableOwnedEnd", attrib={
                etree.QName(namespaces["xmi"], "idref"): owned_end_id,
            })
            member_end_ids.append(owned_end_id)
        
        return {
            "member_end_ids": member_end_ids
        }
    
    elif relationship_type in [
        "Association", "Aggregation", "Composition", "DirectedAssociation",
        "DirectedAggregation", "DirectedComposition"
    ]:
        assoc_elem = find_element_by_id(relationship_id, parent_elem, top_node=model_elem)
        if assoc_elem is not None:
            return  {
                "member_end_ids": [
                    get_attribute_with_ns("idref", end)
                    for end in assoc_elem.findall("memberEnd")
                ]
            }
        assoc_attrib = {
            etree.QName(namespaces["xmi"], "type"): "uml:Association",
            etree.QName(namespaces["xmi"], "id"): relationship_id,
            "name": relationship.get("name", "")
        }
        assoc_elem = create_sub_element(parent_elem, "packagedElement", attrib=assoc_attrib)

        owned_attr_for_target = None
        for attr in source_elem.findall("ownedAttribute"):
            if attr.get("type") == target_id:
                owned_attr_for_target = attr
                break
        if owned_attr_for_target is not None and "association" not in owned_attr_for_target.attrib:
            owned_attr_for_target.set("association", relationship_id)
        else:
            # Create ownedAttribute in source element if not found
            attr_attrib = {
                etree.QName(namespaces["xmi"], "type"): "uml:Property",
                etree.QName(namespaces["xmi"], "id"): gen_id(),
                "name": relationship.get("target", {}).get("name", ""),
                "visibility": "public",
                "type": target_id,
                "association": relationship_id
            }
            owned_attr_for_target = create_sub_element(source_elem, "ownedAttribute", attrib=attr_attrib)

        # Aggregation
        if relationship.get("type", "").endswith("Composition"):
            owned_attr_for_target.set("aggregation", "composite")
        elif relationship.get("type", "").endswith("Aggregation"):
            owned_attr_for_target.set("aggregation", "shared")

        # Member Ends
        member_end_ids = [get_attribute_with_ns("id", owned_attr_for_target),]
        if relationship.get("type", "").startswith("Directed"):
            # Directed Association
            owned_end_attrib_id = gen_id()
            owned_end_attrib = {
                etree.QName(namespaces["xmi"], "type"): "uml:Property",
                etree.QName(namespaces["xmi"], "id"): owned_end_attrib_id,
                "visibility": "public",
                "type": source_id,
                "association": relationship_id
            }
            owned_end_elem = create_sub_element(assoc_elem, "ownedEnd", attrib=owned_end_attrib)
            create_multiplicity(relationship.get("source", {}).get("multiplicity", None), owned_end_elem)
            member_end_ids.append(owned_end_attrib_id)
        else:
            # Undirected Association
            owned_attr_for_source = None
            for attr in target_elem.findall("ownedAttribute"):
                if attr.get("type") == source_id:
                    owned_attr_for_source = attr
                    break
            if owned_attr_for_source is not None and "association" not in owned_attr_for_source.attrib:
                owned_attr_for_source.set("association", relationship_id)
            else:
                # Create ownedAttribute in target element if not found
                attr_attrib = {
                    etree.QName(namespaces["xmi"], "type"): "uml:Property",
                    etree.QName(namespaces["xmi"], "id"): gen_id(),
                    "name": relationship.get("source", {}).get("name", ""),
                    "visibility": "public",
                    "type": source_id,
                    "association": relationship_id
                }
                owned_attr_for_source = create_sub_element(target_elem, "ownedAttribute", attrib=attr_attrib)
                create_multiplicity(relationship.get("source", {}).get("multiplicity", None), owned_attr_for_source)
            member_end_ids.append(get_attribute_with_ns("id", owned_attr_for_source))

        for idref in member_end_ids:
            end_attrib = {
                etree.QName(namespaces["xmi"], "idref"): idref,
            }
            create_sub_element(assoc_elem, "memberEnd", attrib=end_attrib)
        
        return {
            "member_end_ids": member_end_ids
        }
    
    elif relationship_type == "Extend":
        extend_elem = find_element_by_id(relationship_id, source_elem)
        if extend_elem is None:
            extend_elem = create_sub_element(source_elem, "extend", attrib={
                etree.QName(namespaces["xmi"], "type"): "uml:Extend",
                etree.QName(namespaces["xmi"], "id"): relationship_id,
                "visibility": "public",
                "extendedCase": target_id
            })
        return {}
    
    elif relationship_type == "Include":
        include_elem = find_element_by_id(relationship_id, source_elem)
        if include_elem is None:
            include_elem = create_sub_element(source_elem, "include", attrib={
                etree.QName(namespaces["xmi"], "type"): "uml:Include",
                etree.QName(namespaces["xmi"], "id"): relationship_id,
                "visibility": "public",
                "addition": target_id
            })
        return {}
    
    elif relationship_type == "Abstraction":
        abstraction_elem = find_element_by_id(relationship_id, parent_elem, top_node=model_elem)
        if abstraction_elem is None:
            abstraction_elem = create_sub_element(parent_elem, "packagedElement", attrib={
                etree.QName(namespaces["xmi"], "type"): "uml:Abstraction",
                etree.QName(namespaces["xmi"], "id"): relationship_id,
                "name": relationship.get("name", "")
            })
            create_sub_element(abstraction_elem, "client", attrib={
                etree.QName(namespaces["xmi"], "idref"): source_id
            })
            create_sub_element(abstraction_elem, "supplier", attrib={
                etree.QName(namespaces["xmi"], "idref"): target_id
            })
        return {}
    
    elif relationship_type == "Dependency":
        dependency_elem = find_element_by_id(relationship_id, parent_elem, top_node=model_elem)
        if dependency_elem is None:
            dependency_elem = create_sub_element(parent_elem, "packagedElement", attrib={
                etree.QName(namespaces["xmi"], "type"): "uml:Dependency",
                etree.QName(namespaces["xmi"], "id"): relationship_id,
                "name": relationship.get("name", "")
            })
            create_sub_element(dependency_elem, "client", attrib={
                etree.QName(namespaces["xmi"], "idref"): source_id
            })
            create_sub_element(dependency_elem, "supplier", attrib={
                etree.QName(namespaces["xmi"], "idref"): target_id
            })
        return {}
    # TODO: Check why dependencies are not shown when one end is a relationship
    
    elif relationship_type == "AssociationClass":
        assoc_elem = find_element_by_id(relationship_id, parent_elem, top_node=model_elem)
        if assoc_elem is None:
            assoc_elem = create_class(
                {
                    "id": relationship_id,
                    "name": relationship.get("name", ""),
                },
                parent_elem,
                xmi_type="uml:AssociationClass"
            )
        else:
            assoc_elem.set(etree.QName(namespaces["xmi"], "type"), "uml:AssociationClass")

        member_end_ids = []
        for end_id in [source_id, target_id]:
            create_sub_element(assoc_elem, "memberEnd", attrib={
                etree.QName(namespaces["xmi"], "idref"): end_id,
            })
            owned_attr = None
            attr_parent = target_elem if end_id == source_id else source_elem
            for attr in attr_parent.findall("ownedAttribute"):
                if attr.get("type") == end_id:
                    owned_attr = attr
                    break
            if owned_attr is None:
                # Create ownedAttribute in association class if not found
                attr_attrib = {
                    etree.QName(namespaces["xmi"], "type"): "uml:Property",
                    etree.QName(namespaces["xmi"], "id"): gen_id(),
                    "name": relationship.get("source" if end_id == source_id else "target", {}).get("name", ""),
                    "visibility": "public",
                    "type": end_id
                }
                owned_attr = create_sub_element(attr_parent, "ownedAttribute", attrib=attr_attrib)
                create_multiplicity(relationship.get("source" if end_id == source_id else "target", {}).get("multiplicity", None), owned_attr)
            owned_attr.set("association", relationship_id)
            member_end_id = get_attribute_with_ns("id", owned_attr)
            member_end_ids.append(member_end_id)
            create_stereotypes(
                member_end_id,
                ["ParticipantProperty"],
                root,
                tagged_values={"end": end_id}
            )
        return {
            "member_end_ids": member_end_ids
        }
    
    elif relationship_type == "Containment":
        if target_elem.getparent() == source_elem:
            return {}
        if get_attribute_with_ns("type", source_elem) == "uml:Class":
            target_elem.tag = "nestedClassifier"
        source_elem.append(target_elem)
        return {}
    
def resort_relationships(diagram):
    # Ensure IDs exist
    rels = diagram.get("relationships", [])
    for r in rels:
        if "id" not in r: r["id"] = gen_id()

    sorted_list = []
    seen_ids = set()
    remaining = {r["id"]: r for r in rels}

    # Keep looping as long as we are still adding relationships
    while remaining:
        start_count = len(remaining)
        for rid, r in list(remaining.items()):
            # A relationship is "ready" if its source/target aren't pointing to 
            # other relationships that haven't been added to sorted_list yet.
            deps = {r.get("source", {}).get("idref"), r.get("target", {}).get("idref")}
            if not (deps & set(remaining.keys())):
                sorted_list.append(remaining.pop(rid))
                seen_ids.add(rid)
        
        # Break if we hit a circular dependency to avoid infinite loop
        if len(remaining) == start_count:
            sorted_list.extend(remaining.values())
            break

    diagram["relationships"] = sorted_list
    return diagram

    