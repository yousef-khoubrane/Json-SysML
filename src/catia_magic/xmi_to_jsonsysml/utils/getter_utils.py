
from utils.helpers import (
    namespaces,
    all_ns,
    smart_cast,
    remove_html_tags
)

from tqdm import tqdm

SEEN_ELEMENTS = {}

def find_root_model(tree):
    """
    Finds the root <uml:Model> element in the provided XML tree.
    """
    for elem in tree.iter():
        if elem.tag.endswith("Model"):
            return elem
    raise ValueError("No <uml:Model> element found in XMI template.")

def find_element_by_id(element_id, parent, fallback=None):
    """
    Finds an element by xmi:id, searching:
    - current node + its subtree
    - then each ancestor, excluding already visited subtrees
    """
    if not isinstance(element_id, str):
        return fallback
    
    seen = SEEN_ELEMENTS.get(element_id, "not found")
    if seen == None:
        return fallback
    elif seen != "not found":
        return seen

    current = parent
    excluded = None
    xpath_expr = f"self::*[@xmi:id='{element_id}'] | .//*[@xmi:id='{element_id}']"

    while current is not None:
        for ns in all_ns:
            # Check the current ancestor itself first!
            self_match = current.xpath(f"self::*[@xmi:id='{element_id}']", namespaces=ns)
            if self_match:
                SEEN_ELEMENTS[element_id] = self_match[0]
                return self_match[0]

            if excluded is None:
                # FIRST PASS: Search the starting node and its entire subtree
                elements = current.xpath(xpath_expr, namespaces=ns)
                if elements:
                    SEEN_ELEMENTS[element_id] = elements[0]
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
                        SEEN_ELEMENTS[element_id] = elements[0]
                        return elements[0]

        # Move up the tree
        excluded = current
        current = current.getparent()

    # tqdm.write(f"No element found with xmi:id == {element_id}")
    SEEN_ELEMENTS[element_id] = None
    return fallback

def get_attribute_with_ns(name, element):
    """
    Retrieves an attribute from an XML element, considering namespaces.

    Args:
        name (str): The name of the attribute, possibly with a namespace prefix (e.g., "xmi:id").
        element (Element): The XML element from which to retrieve the attribute.

    Returns:
        any: The value of the attribute if found, or None if not found.
    """
    if element is None:
        return None
    ns_name = "xmi"
    attribute = name
    if ":" in name:
        ns_name = name.split(":")[0]
        attribute = name.split(":")[1]
    for ns in all_ns:
        attr = element.get(f"{{{ns[ns_name]}}}{attribute}")
        if attr is not None:
            return attr
    return None

def get_element_stereotypes(element, extract_tagged_values=False, return_full_stereotypes=False):
    """
    Retrieves the stereotypes of a SysML element.

    Args:
        element (Element): The corresponding XML element.

    Returns:
        list: A list of stereotypes associated with the element.
    """
    if element is None:
        if extract_tagged_values:
            return [], {}
        return []
    root = element.getroottree().getroot()
    stereotypes = []
    tagged_values = {}
    xmi_type = get_attribute_with_ns("type", element)
    if not xmi_type:
        if extract_tagged_values:
            return [], {}
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
            # Only add the last part of the tag (e.g., "Block" instead of "sysml:Block")
            stereotypes.extend([el.tag.split("}")[-1] for el in elements])

    # The previous stereotypes belong to SysML and UML. If you want to also include the ones belonging
    # to the modeling tool (e.g., MagicDraw), you can change or remove the conditions below:
    more_elements = []
    if xmi_type == "uml:Comment":
        more_elements = root.xpath(f"./*[@base_Element='{get_attribute_with_ns('id', element)}']")
        if more_elements:
            if return_full_stereotypes:
                stereotypes.extend(
                    [
                        el.tag
                        for el in more_elements
                        if el.tag.split("}")[-1] in ["Previous", "Next", "diagramDescription"]
                    ]
                )
            else:
                stereotypes.extend(
                    [
                        el.tag.split("}")[-1]
                        for el in more_elements
                        if el.tag.split("}")[-1] in ["Previous", "Next", "diagramDescription"]
                    ]
                )
    
    if extract_tagged_values:
        all_elements = elements + [el for el in more_elements if el.tag.split("}")[-1] in ["diagramDescription"]]
        for el in all_elements:
            tagged_values.update(
                {
                    remove_html_tags(key): remove_html_tags(value)
                    for key, value in el.attrib.items()
                    if (
                        key not in ["base_Element", f"base_{rename(xmi_type.split(':')[-1])}"]
                        and "{" not in key
                    )
                }
            )
        is_likely_id = lambda x: isinstance(x, str) and " " not in x and "_" in x
        for key, value in tagged_values.items():
            if is_likely_id(value):
                value_element = find_element_by_id(value, root)
                if value_element is not None:
                    tagged_values[key] = {
                        "name": value_element.get("name"),
                        "idref": value,
                    }
                    value_element_type = value_element.get("type")
                    if value_element_type:
                        type_element = find_element_by_id(value_element_type, root)
                        if type_element is not None:
                            tagged_values[key]["type"] = {
                                "name": type_element.get("name"),
                                "idref": value_element_type,
                            }
                    if value_element.get("value"):
                        tagged_values[key]["value"] = smart_cast(value_element.get("value"))
                    if value_element.get("body"):
                        tagged_values[key]["body"] = remove_html_tags(value_element.get("body"))

    if xmi_type == "uml:AssociationClass":
        stereotypes.append("AssociationBlock")

    if extract_tagged_values:
        return stereotypes, tagged_values
    return stereotypes

def get_element_owner(owner_id, root):
    """
    Retrieves the owner of an element by its owner ID.
    The owner is traversed up the XML tree to construct a path.
    """
    path = ""
    id_path = ""
    owner = find_element_by_id(owner_id, root)
    while owner is not None and get_attribute_with_ns("id", owner) is not None and owner.getparent() is not None:
        path = owner.get("name", "") + "::" + path
        id_path = get_attribute_with_ns("id", owner) + "::" + id_path
        owner = owner.getparent()
    path = path[:-2]
    id_path = id_path[:-2]
    return {"path": path, "idPath": id_path}

def get_feature_direction(element):
    """
    Retrieves the direction of a directed feature by its base_Feature ID.
    """
    id = get_attribute_with_ns("id", element)
    elements = element.getroottree().getroot().xpath(f"./sysml:DirectedFeature[@base_Feature='{id}']", namespaces=namespaces)
    if elements:
        if len(elements) > 1:
            tqdm.write(f"Found {len(elements)} directed features with base_Feature == {id}. Returned the direction of the first occurence.")
        return elements[0].get("featureDirection")
    return ""

def get_referent_path(element, return_full_path=False):
    """
    Retrieves the referent path of an element.
    """
    predefined_types = ["String", "Real", "Number", "Complex", "Integer", "Boolean", "VerdictKind", "void"]
    rp = element.get("referentPath", "")
    if return_full_path:
        return rp
    shortened_rp = rp.split("::")[-1]
    if shortened_rp in predefined_types:
        return shortened_rp
    elif any(rp.startswith(prefix) for prefix in ["QUDV::", "SIDefinitions::"]):
        return shortened_rp
    return rp

def get_flow_property_direction(element):
    """
    Retrieves the direction of a flow property by its base_Property ID.
    """
    id = get_attribute_with_ns("id", element)
    elements = element.getroottree().getroot().xpath(f"./sysml:FlowProperty[@base_Property='{id}']", namespaces=namespaces)
    if elements:
        if len(elements) > 1:
            tqdm.write(f"Found {len(elements)} flow properties with base_Property == {id}. Returned the direction of the first occurence.")
        return elements[0].get("direction")
    return ""

def get_multiplicity(element):
    """
    Helper function to retrieve the multiplicity of a SysML element.
    """
    min_mult, max_mult = None, None
    lower_value_default = "*"
    upper_value_default = "*"
    try:
        lower_value_elem = element.find("lowerValue")
        if lower_value_elem is None:
            lower_value_elem = element.xpath("./xmi:Extension/modelExtension/lowerValue", namespaces=namespaces)[0]
        if get_attribute_with_ns("type", lower_value_elem) == "uml:LiteralInteger":
            lower_value_default = 0
            upper_value_default = 0
        min_mult = lower_value_elem.get("value", lower_value_default)
        min_mult = smart_cast(min_mult)
    except (TypeError, IndexError, AttributeError):
        pass
    try:
        upper_value_elem = element.find("upperValue")
        if upper_value_elem is None:
            upper_value_elem = element.xpath("./xmi:Extension/modelExtension/upperValue", namespaces=namespaces)[0]
        max_mult = upper_value_elem.get("value", upper_value_default)
        max_mult = smart_cast(max_mult)
    except (TypeError, IndexError, AttributeError):
        pass

    if min_mult == None and max_mult == None:
        return None
    
    if min_mult == None:
        min_mult = 0
    if max_mult == None:
        max_mult = "*"

    multiplicity = ""
    if min_mult == max_mult:
        multiplicity = min_mult
    else:
        multiplicity = f"{min_mult}..{max_mult}"
    # # Either that way or:
    # multiplicity = {"min": min_mult, "max": max_mult}
    return multiplicity

def get_type(element):
    """
    Retrieves the type of a SysML element.

    Args:
        element (Element): The XML element from which to extract the type.

    Returns:
        dict: A dictionary containing the type name (and ID if available), or {} if no type is found.
    """
    type = {}
    if element is None:
        return type

    if element.get("type"):
        type_el = find_element_by_id(
            element.get("type"),
            element.getparent(),
            fallback={}
        )
        type = {
            "name": type_el.get("name"),
            "idref": element.get("type")
        }

        if get_attribute_with_ns("type", type_el) == "uml:DataType":
            _, tagged_values = get_element_stereotypes(type_el, extract_tagged_values=True)
            if "unit" in tagged_values:
                type["unit"] = tagged_values["unit"]

            try:
                type["generalization"] = get_referent_path(type_el.find("generalization")[0][0][0])
            except (TypeError, IndexError, AttributeError):
                pass

    elif element.xpath("./type"):
        try:
            type_name = get_referent_path(element.find("type")[0][0])
            type = {"name": type_name}
        except (TypeError, IndexError, AttributeError):
            pass

    return type

def get_boolean_values(element):
    """
    Retrieves boolean values from an XML element's attributes.

    Args:
        element (Element): The XML element from which to extract boolean values.

    Returns:
        dict: A dictionary containing the boolean attributes and their values.
    """
    boolean_values = {}
    for attr, value in element.attrib.items():
        if attr.startswith("is") and attr[2].isupper() and value in ["true", "false"]:
            boolean_values[attr] = value.lower() == "true"
    return boolean_values

def get_body_and_language(element, body_owner = None):
    """
    Extracts the body and language from a SysML element.
    """
    value = {}
    body, language = "", ""
    expr = None
    if body_owner == None:
        expr = element
    elif element.xpath(f"./{body_owner}"):
        expr = element.xpath(f"./{body_owner}")[0]
    if expr is not None:
        if expr.xpath("./body"):
            body = remove_html_tags(expr.xpath("./body")[0].text)
        if expr.xpath("./language"):
            language = remove_html_tags(expr.xpath("./language")[0].text)
    if body:
        value["body"] = body
    if language:
        value["language"] = language
    return value