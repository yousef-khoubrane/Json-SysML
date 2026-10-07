
from utils.getter_utils import (
    find_element_by_id,
    get_attribute_with_ns,
    get_element_stereotypes
)
from utils.post_processing import finalize_extraction

def extract_usecase(element):
    """
    Extracts a SysML use case from an XMI element.

    Args:
        element (Element): The XML element representing the use case.

    Returns:
        dict: A dictionary containing the use case information.
    """
    id = get_attribute_with_ns("id", element)
    name = element.get("name")
    usecase = {
        "name": name,
        "id": id,
    }

    extension_points = []
    if element.xpath("./extensionPoint"):
        extension_points = [
            ep.get("name")
            for ep in element.xpath("./extensionPoint")
        ]
    if extension_points:
        usecase["extensionPoints"] = extension_points

    stereotypes, tagged_values = get_element_stereotypes(element, extract_tagged_values=True)
    usecase["stereotypes"], usecase["taggedValues"] = stereotypes, tagged_values

    usecase = finalize_extraction(element, usecase)
    return usecase

def extract_uc_relationship(element):
    """
    Extracts a SysML use case relationship from an XMI element.

    Args:
        element (Element): The XML element representing the use case relationship.

    Returns:
        dict: A dictionary containing the use case relationship information.
    """
    relationship = {
        "id": get_attribute_with_ns("id", element),
        "name": element.get("name"),
    }

    xmi_type = get_attribute_with_ns("type", element)
    source = {
        "name": element.getparent().get("name"),
        "idref": get_attribute_with_ns("id", element.getparent()),
    }
    target = None
    if xmi_type == "uml:Extend" and element.get("extendedCase"):
        relationship["type"] = "Extend"
        target = {
            "name": find_element_by_id(element.get("extendedCase"), element.getparent(), {}).get("name"),
            "idref": element.get("extendedCase")
        }
    elif xmi_type == "uml:Include" and element.get("addition"):
        relationship["type"] = "Include"
        target = {
            "name": find_element_by_id(element.get("addition"), element.getparent(), {}).get("name"),
            "idref": element.get("addition")
        }
    relationship["source"], relationship["target"] = source, target

    relationship = finalize_extraction(element, relationship)
    return relationship