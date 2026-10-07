
from utils.getter_utils import (
    get_attribute_with_ns,
    get_element_owner,
    get_element_stereotypes,
)
from utils.post_processing import finalize_extraction

def extract_package(element):
    """
    Extracts a SysML package from an XMI element.

    Args:
        element (Element): The XML element representing the package.

    Returns:
        dict: A dictionary containing the package information.
    """
    id = get_attribute_with_ns("id", element)
    name = element.get("name")
    owner = get_element_owner(get_attribute_with_ns("id", element.getparent()), element.getparent())
    stereotypes = get_element_stereotypes(element)

    package = {
        "name": name,
        "id": id,
        "owner": owner,
        "stereotypes": stereotypes
    }

    xmi_type = get_attribute_with_ns("type", element)
    if xmi_type == "uml:Model":
        package["isModel"] = True

    package = finalize_extraction(element, package)
    return package