
from utils.helpers import (
    smart_cast,
    remove_html_tags,
    all_ns
)
from utils.getter_utils import (
    find_element_by_id,
    get_attribute_with_ns,
    get_element_stereotypes,
    get_multiplicity,
    get_referent_path,
)
from utils.post_processing import finalize_extraction

def extract_comment(element):
    """
    Extracts a comment from an XML element.

    Args:
        element (Element): The XML element representing the comment.

    Returns:
        dict: A dictionary containing the comment information.
    """
    stereotypes, tagged_values = get_element_stereotypes(element, extract_tagged_values=True)
    def get_idref(el):
        idref = get_attribute_with_ns("idref", el)
        if not idref:
            href = el.get("href")
            if href and "#" in href and not href.startswith("http://"):
                idref = href.split("#")[-1]
            else:
                try:
                    ref_ext = el[0][0]
                    idref = ref_ext.get("originalID")
                except (TypeError, IndexError, AttributeError):
                    pass
        return idref
    
    comment = {
        "body": remove_html_tags(element.get("body", "")).strip(),
        "stereotypes": stereotypes,
        "taggedValues": tagged_values,
        "annotatedElements": [
            get_idref(el) for el in element.findall("annotatedElement")
        ],
    }
    comment = finalize_extraction(element, comment)
    return comment

def extract_relationship(element):
    """
    Extracts a SysML relationship from an XMI element.

    Args:
        element (Element): The XML element representing the relationship.

    Returns:
        dict: A dictionary containing the relationship information.
    """

    root = element.getparent()
    xmi_type = get_attribute_with_ns("type", element)
    relationship = {
        "name": element.get("name"),
        "id": get_attribute_with_ns("id", element),
        "type": xmi_type.split(":")[-1],
        "stereotypes": get_element_stereotypes(element),
        "source": None,
        "target": None,
    }

    if xmi_type == "uml:Association":

        is_directed = False
        aggregation = None

        if element.xpath("./ownedEnd") and len(element.xpath("./ownedEnd")) == 1:
            is_directed = True
            memberends = element.xpath("./memberEnd")
            if len(memberends) == 2:
                target_attribute_id = get_attribute_with_ns("idref", memberends[0])
                ownedend = element.xpath("./ownedEnd")[0]
                if target_attribute_id == get_attribute_with_ns("id", ownedend):
                    target_attribute_id = get_attribute_with_ns("idref", memberends[1])
                target_attribute = find_element_by_id(target_attribute_id, root)
                if target_attribute is not None:
                    target_element = find_element_by_id(target_attribute.get("type"), root, {})
                    aggregation = target_attribute.get("aggregation")
                    relationship["source"] = {
                        "name": target_attribute.getparent().get("name"),
                        "idref": get_attribute_with_ns("id", target_attribute.getparent())
                    }
                    relationship["target"] = {
                        "name": target_element.get("name"),
                        "idref": target_attribute.get("type")
                    }
                    source_multiplicity = get_multiplicity(ownedend)
                    if source_multiplicity is not None:
                        relationship["source"]["multiplicity"] = source_multiplicity
                    target_multiplicity = get_multiplicity(target_attribute)
                    if target_multiplicity is not None:
                        relationship["target"]["multiplicity"] = target_multiplicity

        if not is_directed:
            ownedends = element.xpath("./ownedEnd")
            if ownedends and len(ownedends) == 2:
                for idx, ownedend in enumerate(ownedends):
                    if aggregation is None:
                        aggregation = ownedend.get("aggregation")
                    key = "source" if idx == 0 else "target"
                    end_element = find_element_by_id(ownedend.get("type"), root)
                    relationship[key] = {
                        "name": end_element.get("name"),
                        "idref": ownedend.get("type")
                    }
                    multiplicity = get_multiplicity(ownedend)
                    if multiplicity is not None:
                        relationship[key]["multiplicity"] = multiplicity
            else:
                memberends = element.xpath("./memberEnd")
                if len(memberends) == 2:
                    members = [find_element_by_id(get_attribute_with_ns("idref", memberends[i]), root) for i in range(2)]
                    keys = ["source", "target"]
                    multiplicities = {}
                    for idx, member in enumerate(members):
                        if member.tag == "ownedAttribute":
                            if aggregation is None:
                                aggregation = member.get("aggregation")
                            relationship[keys[idx]] = {
                                "name": member.getparent().get("name"),
                                "idref": get_attribute_with_ns("id", member.getparent())
                            }
                            multiplicity = get_multiplicity(member)
                            if multiplicity is not None:
                                multiplicities[keys[1-idx]] = multiplicity
                    for key in keys:
                        if key in multiplicities:
                            relationship[key]["multiplicity"] = multiplicities[key]

        relationship_type_prefix = "Directed" if is_directed else ""
        if aggregation is None:
            relationship["type"] = f"{relationship_type_prefix}Association"
        elif aggregation == "composite":
            relationship["type"] = f"{relationship_type_prefix}Composition"
        elif aggregation == "shared":
            relationship["type"] = f"{relationship_type_prefix}Aggregation"

    elif xmi_type == "uml:Generalization":

        parent = element.getparent()
        relationship["source"] = {
            "name": parent.get("name"),
            "idref": get_attribute_with_ns("id", parent)
        }
        target_id = element.get("general")
        if not target_id:
            try:
                target_id = element.find("generalization")[0][0][0].get("originalID")
            except (TypeError, IndexError, AttributeError):
                pass

        if target_id:
            target_element = find_element_by_id(target_id, root)
            relationship["target"] = {
                "name": target_element.get("name"),
                "idref": target_id
            }

    elif xmi_type == "uml:AssociationClass":

        relationship["type"] = "AssociationClass"
        owned_ends = element.xpath("./ownedEnd")
        if owned_ends and len(owned_ends) == 2:
            ids = [element.xpath("./ownedEnd")[i].get("type") for i in range(2)]
            ends = [
                {
                    "name": find_element_by_id(id, root).get("name"),
                    "idref": id
                } for id in ids
            ]
            relationship["source"], relationship["target"] = ends
        else:
            member_ends = element.xpath("./memberEnd")
            if member_ends and len(member_ends) == 2:
                ids = [get_attribute_with_ns("idref", element.xpath("./memberEnd")[i]) for i in range(2)]
                ends = []
                for id in ids:
                    attribute = find_element_by_id(id, root)
                    parent = attribute.getparent()
                    ends.append({
                        "name": parent.get("name"),
                        "idref": get_attribute_with_ns("id", parent),
                        "multiplicity": get_multiplicity(attribute),
                    })
                relationship["source"], relationship["target"] = ends

    elif xmi_type == "uml:InformationFlow":

        relationship["type"] = "ItemFlow"
        source_id = get_attribute_with_ns("idref", element.find("informationSource"))
        target_id = get_attribute_with_ns("idref", element.find("informationTarget"))
        if source_id:
            source_element = find_element_by_id(source_id, root)
            relationship["source"] = {
                "name": source_element.get("name"),
                "idref": source_id
            }
        if target_id:
            target_element = find_element_by_id(target_id, root)
            relationship["target"] = {
                "name": target_element.get("name"),
                "idref": target_id
            }

    elif xmi_type == "uml:Usage":

        client_id = get_attribute_with_ns("idref", element.find("client"))
        if client_id:
            client_element = find_element_by_id(client_id, root)
            relationship["source"] = {
                "name": client_element.get("name"),
                "idref": client_id
            }

        supplier_id = get_attribute_with_ns("idref", element.find("supplier"))
        if supplier_id:
            supplier_element = find_element_by_id(supplier_id, root)
            relationship["target"] = {
                "name": supplier_element.get("name"),
                "idref": supplier_id
            }

    elif xmi_type == "uml:InterfaceRealization":

        parent = element.getparent()
        relationship["source"] = {
            "name": parent.get("name"),
            "idref": get_attribute_with_ns("id", parent)
        }
        supplier_id = get_attribute_with_ns("idref", element.find("supplier"))
        if supplier_id:
            supplier_element = find_element_by_id(supplier_id, root)
            relationship["target"] = {
                "name": supplier_element.get("name"),
                "idref": supplier_id
            }

    elif xmi_type in ["uml:Dependency", "uml:Abstraction"]:

        client_id = get_attribute_with_ns("idref", element.find("client"))
        if client_id:
            client_element = find_element_by_id(client_id, root)
            relationship["source"] = {
                "name": client_element.get("name"),
                "idref": client_id
            }
        supplier_id = get_attribute_with_ns("idref", element.find("supplier"))
        if supplier_id:
            supplier_element = find_element_by_id(supplier_id, root)
            relationship["target"] = {
                "name": supplier_element.get("name"),
                "idref": supplier_id
            }

    elif xmi_type == "uml:PackageImport":

        relationship["source"] = {
            "name": element.getparent().get("name"),
            "idref": get_attribute_with_ns("id", element.getparent())
        }
        if element.get("importedPackage"):
            imported_package_element = find_element_by_id(
                element.get("importedPackage"),
                element.getparent()
            )
            relationship["target"] = {
                "name": imported_package_element.get("name"),
                "idref": element.get("importedPackage")
            }
        elif element.xpath("./importedPackage"):
            try:
                ref_extension = element.find("importedPackage")[0][0]
                relationship["target"] = {
                    "name": get_referent_path(ref_extension, return_full_path=True),
                    "originalID": ref_extension.get("originalID")
                }
            except (TypeError, IndexError, AttributeError):
                pass      

    relationship = finalize_extraction(element, relationship)
    return relationship

def extract_containment_relationships(diagram, root):
    """
    Extracts containment relationships from a SysML diagram.

    Args:
        diagram (Element): The XML element representing the SysML diagram.
        root (Element): The root XML element of the XMI document.
    """
    diagram_owned_views = None
    for ns in all_ns:
        diagram_frames = root.xpath(f"./xmi:Extension/filePart/mdOwnedViews/mdElement[@elementClass='DiagramFrame']/elementID[@xmi:idref='{diagram.get('id')}']", namespaces=ns)
        if diagram_frames:
            diagram_owned_views = diagram_frames[0].getparent().getparent()
            if not diagram_owned_views.tag == "mdOwnedViews":
                diagram_owned_views = None
            break

    if diagram_owned_views is None:
        return
    
    for containment_md_element in diagram_owned_views.findall(".//mdElement[@elementClass='ContainmentLink']"):
        relationship = {
            "type": "Containment",
        }
        source_md_id = get_attribute_with_ns("idref", containment_md_element.find("./linkFirstEndID"))
        target_md_id = get_attribute_with_ns("idref", containment_md_element.find("./linkSecondEndID"))
        for key, md_id in [("source", source_md_id), ("target", target_md_id)]:
            md_element = find_element_by_id(md_id, diagram_owned_views)
            if md_element is not None:
                element_idref = get_attribute_with_ns("idref", md_element.find("./elementID"))
                element = find_element_by_id(element_idref, root)
                if element is not None:
                    relationship[key] = {
                        "name": element.get("name"),
                        "idref": element_idref
                    }
        if "source" in relationship and "target" in relationship:
            diagram.setdefault("relationships", []).append(relationship)

def extract_geometry_info(md_element, fallback=(0, 0)):
    """
    Extracts geometry information from a MagicDraw diagram element.

    Args:
        md_element (Element): The MagicDraw diagram element containing geometry information.
        fallback (tuple): A tuple representing the fallback coordinates (x, y) if extraction fails.

    Returns:
        geometry_info (dict): A dictionary containing the A_Coordinates and B_Coordinates.
    """
    geometry_info = {}
    try:
        geometry = md_element.xpath("./geometry")[0].text.strip()
        if ";" in geometry:
            geometry = geometry.replace(";", ",")
            A_x, A_y, B_x, B_y = [smart_cast(n.strip()) for n in geometry.split(",")[:4]]
            geometry_info["A_Coordinates"] = [A_x, A_y]
            geometry_info["B_Coordinates"] = [B_x, B_y]
        else:
            x, y, width, height = [smart_cast(n.strip()) for n in geometry.split(",")[:4]]
            geometry_info["A_Coordinates"] = [x, y]
            geometry_info["B_Coordinates"] = [x + width, y + height]
    except (IndexError, ValueError):
        geometry_info["A_Coordinates"] = fallback
        geometry_info["B_Coordinates"] = fallback
    return geometry_info