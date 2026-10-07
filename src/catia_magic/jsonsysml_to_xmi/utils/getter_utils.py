
from utils.helpers import all_ns
import utils.variables as VARIABLES

from tqdm import tqdm

def find_root_model(tree):
    for elem in tree.iter():
        if elem.tag.endswith("Model"):
            return elem
    raise ValueError("No <uml:Model> element found in XMI template.")

def find_element_by_id(element_id, parent, top_node=None, fallback=None, only_search_created_nodes=True):
    """
    Finds an element by xmi:id, searching upwards through the tree if necessary.
    """
    if not isinstance(element_id, str):
        return fallback
    
    if only_search_created_nodes: 
        # Set this to `False` if you do not start from an empty template or if your model
        # uses or references elements from profiles in your XMI template
        return VARIABLES.CREATED_NODES.get(element_id, fallback)
    
    elif element_id in VARIABLES.CREATED_NODES:
        return VARIABLES.CREATED_NODES[element_id]

    current = parent
    excluded = None
    xpath_expr = f"self::*[@xmi:id='{element_id}'] | .//*[@xmi:id='{element_id}']"

    if top_node is not None:
        top_node = top_node.getparent()

    while current is not top_node:
        for ns in all_ns:
            # Check the current ancestor itself first!
            # Your previous version only checked 'current' in the first iteration.
            # In subsequent iterations, it only checked 'current's children.
            self_match = current.xpath(f"self::*[@xmi:id='{element_id}']", namespaces=ns)
            if self_match:
                return self_match[0]

            if excluded is None:
                # FIRST PASS: Search the starting node and its entire subtree
                elements = current.xpath(xpath_expr, namespaces=ns)
                if elements:
                    return elements[0]
            else:
                # UPWARD PASS: Search all siblings (other children of the current parent)
                for child in current:
                    if child == excluded:
                        continue
                    
                    elements = child.xpath(xpath_expr, namespaces=ns)
                    if elements:
                        if len(elements) > 1:
                            tqdm.write(f"Found {len(elements)} elements with ID {element_id}.")
                        return elements[0]
                    
        # Move up the tree
        excluded = current
        current = current.getparent()

    return fallback

def get_attribute_with_ns(name, element, fallback=None):
    """
    Retrieves an attribute from an XML element, considering namespaces.

    Args:
        name (str): The name of the attribute, possibly with a namespace prefix (e.g., "xmi:id").
        element (Element): The XML element from which to retrieve the attribute.

    Returns:
        any: The value of the attribute if found, or `fallback` if not found.
    """
    ns_name = "xmi"
    attribute = name
    if ":" in name:
        ns_name = name.split(":")[0]
        attribute = name.split(":")[1]
    for ns in all_ns:
        attr = element.get(f"{{{ns[ns_name]}}}{attribute}")
        if attr is not None:
            return attr
    return fallback

def get_closest_package(element):
    """
    Traverses up the XML tree to find the closest ancestor element that is a UML Package.

    Args:
        element (Element): The starting XML element.

    Returns:
        Element: The closest ancestor element that is a UML Package, or None if no such element is found.
    """
    pkg_element = element
    while pkg_element is not None and get_attribute_with_ns("type", pkg_element) not in ["uml:Package", "uml:Model"]:
        pkg_element = pkg_element.getparent()
    if pkg_element is None:
        pkg_element = find_root_model(element.getroottree().getroot())
    return pkg_element

def get_element_stereotypes(element, return_full_stereotypes=False):
    """
    Retrieves the stereotypes of a SysML element.

    Args:
        element (Element): The corresponding XML element.
        return_full_stereotypes (Boolean): If false, only returns the last part of the stereotype (e.g., "Block" instead of "sysml:Block").

    Returns:
        list: A list of stereotypes associated with the element.
    """
    if element is None:
        return []
    root = element.getroottree().getroot()
    stereotypes = []
    xmi_type = get_attribute_with_ns("type", element)
    if not xmi_type:
        return []
    name_mapping = {
        "Activity": "Behavior",
        "Component": "Class",
    }
    def rename(x):
        if x in name_mapping:
            return name_mapping[x]
        elif x.endswith("Node"):
            return "ObjectNode"
        elif x.endswith("Action"):
            return "Action"
        else:
            return x

    elements = root.xpath(f"./*[@base_{rename(xmi_type.split(':')[-1])}='{get_attribute_with_ns('id', element)}']")
    if elements:
        if return_full_stereotypes:
            stereotypes.extend([el.tag for el in elements])
        else:
            stereotypes.extend([el.tag.split("}")[-1] for el in elements])

    return stereotypes

def get_xmi_type_of_value(type, value):
    """
    Determines the XMI type of a value given the its type.

    Args:
        type (any): The type of the value.
        value (any): The value for which to determine the XMI type. Used for fallback.

    Returns:
        str: The XMI type as a string.
    """
    if type and isinstance(type, str):
        xmi_type = {
            "String": "uml:LiteralString",
            "Real": "uml:LiteralReal",
            "Number": "uml:LiteralReal",
            "Complex": "uml:LiteralReal",
            "Integer": "uml:LiteralInteger",
            "Boolean": "uml:LiteralBoolean"
        }
        return xmi_type.get(type, "uml:LiteralString")
    else:
        if isinstance(value, bool):
            return "uml:LiteralBoolean"
        elif isinstance(value, int):
            return "uml:LiteralInteger"
        elif isinstance(value, float):
            return "uml:LiteralReal"
        else:
            return "uml:LiteralString"