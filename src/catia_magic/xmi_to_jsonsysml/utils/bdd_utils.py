
from utils.helpers import smart_cast
from utils.getter_utils import (
    find_element_by_id,
    get_attribute_with_ns,
    get_referent_path,
    get_feature_direction,
    get_element_stereotypes,
    get_body_and_language,
    get_type
)
from utils.ibd_utils import extract_property, extract_port
from utils.post_processing import finalize_extraction

def extract_block(element):
    """
    Extracts a SysML block from an XMI element.

    Args:
        element (Element): The XML element representing the block.

    Returns:
        dict: A dictionary containing the block information.
    """
    # stereotypes = get_element_stereotypes(element, return_full_stereotypes=True)
    # invalid_stereotype = lambda s: True if ("MagicDrawProfile" in s) else False
    # if any(invalid_stereotype(s) for s in stereotypes):
    #     return None
    stereotypes, tagged_values = get_element_stereotypes(element, extract_tagged_values=True)

    properties = []
    ports = []
    constraints = []

    for attribute in element.findall("ownedAttribute"):
        xmi_type = get_attribute_with_ns("type", attribute)
        if xmi_type == "uml:Property":
            properties.append(extract_property(attribute))
        elif xmi_type == "uml:Port":
            ports.append(extract_port(attribute))

    for rule_element in element.findall("ownedRule"):
        try:
            rule = {
                "name": rule_element.get("name"),
                "id": get_attribute_with_ns("id", rule_element),
            }
            spec = get_body_and_language(rule_element, "specification")
            if spec:
                rule["expression"] = spec
            constraints.append(rule)
        except (IndexError, AttributeError):
            pass

    operations = []
    for operation in element.findall("ownedOperation"):
        params = []
        for param in operation.findall("ownedParameter"):
            params.append(extract_parameter(param))
        operation_id = get_attribute_with_ns("id", operation)
        operations.append(
            {
                "name": operation.get("name"),
                "id": operation_id,
                "parameters": params,
                "featureDirection": get_feature_direction(operation)
            }
        )
        
    block = {
        "name": element.get("name"),
        "id": get_attribute_with_ns("id", element),
        "stereotypes": stereotypes,
        "taggedValues": tagged_values,
        "properties": properties,
        "constraints": constraints,
        "operations": operations,
        "ports": ports,
    }

    block = finalize_extraction(element, block)
    return block

def extract_instance(element):
    """
    Extracts a SysML instance from an XMI element.

    Args:
        element (Element): The XML element representing the instance.

    Returns:
        dict: A dictionary containing the instance information.
    """
    slots = []
    for slot in element.findall("slot"):
        slot_name = None
        slot_value = None
        try:
            slot_name = get_referent_path(slot.find("definingFeature")[0][0])
        except (TypeError, IndexError, AttributeError):
            pass
        slot_value = slot.find("value").get("value") if slot.find("value") is not None else None
        if slot_value == None:
            try:
                value_element = slot.find("value")
                slot_value = get_referent_path(value_element[0][0][0])
            except (TypeError, IndexError, AttributeError):
                try:
                    instance_id = slot.find("value").get("instance")
                    value_element = find_element_by_id(instance_id, element.getparent())
                    slot_value = {
                        "name": value_element.get("name"),
                        "idref": instance_id
                    }
                except (TypeError, IndexError, AttributeError):
                    pass
        if slot_name == None and slot.get("definingFeature"):
            slot_name = {
                "name": find_element_by_id(
                    slot.get("definingFeature"),
                    element.getparent(),
                    fallback={}
                ).get("name"),
                "idref": slot.get("definingFeature")
            }
        if slot_name and slot_value:
            slots.append(
                {
                    "id": get_attribute_with_ns("id", slot),
                    "key": slot_name,
                    "value": slot_value
                }
            )

    classifier = None
    try:
        classifier = get_referent_path(element.find("classifier")[0][0])
    except (TypeError, IndexError, AttributeError):
        try:
            classifier_id = get_attribute_with_ns("idref", element.find("classifier"))
            classifier_elem = find_element_by_id(classifier_id, element.getparent())
            classifier = {
                "name": classifier_elem.get("name"),
                "idref": classifier_id
            }
        except (TypeError, IndexError, AttributeError):
            pass

    instance = {
        "name": element.get("name"),
        "id": get_attribute_with_ns("id", element),
        "stereotypes": get_element_stereotypes(element),
        "classifier": classifier,
        "slots": slots
    }

    instance = finalize_extraction(element, instance)
    return instance

def extract_enumeration(element):
    """
    Extracts a SysML enumeration from an XMI element.

    Args:
        element (Element): The XML element representing the enumeration.

    Returns:
        dict: A dictionary containing the enumeration information.
    """
    literals = []
    for literal in element.findall("ownedLiteral"):
        literal_dict = {
            "name": literal.get("name"),
            "id": get_attribute_with_ns("id", literal),
            "value": literal.get("value")
        }
        if literal.xpath("./specification"):
            value = smart_cast(literal.xpath("./specification")[0].get("value"))
            if value:
                literal["value"] = value
        literals.append(literal_dict)

    enumeration = {
        "name": element.get("name"),
        "id": get_attribute_with_ns("id", element),
        "literals": literals
    }

    enumeration = finalize_extraction(element, enumeration)
    return enumeration

def extract_parameter(element):
    """
    Extracts a SysML parameter from an XMI element.

    Args:
        element (Element): The XML element representing the parameter.
    
    Returns:
        dict: A dictionary containing the parameter information.
    """

    default_value = None
    try:
        default_value = element.find("defaultValue").get("value")
        default_value = smart_cast(default_value)
    except (TypeError, IndexError, AttributeError):
        pass

    parameter = {
        "name": element.get("name"),
        "id": get_attribute_with_ns("id", element),
        "direction": element.get("direction", "in"),
        "type": get_type(element),
        "defaultValue": default_value
    }

    parameter = finalize_extraction(element, parameter)
    return parameter