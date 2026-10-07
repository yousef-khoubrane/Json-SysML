
from utils.helpers import smart_cast
from utils.getter_utils import (
    find_element_by_id,
    get_attribute_with_ns,
    get_type
)
from utils.post_processing import finalize_extraction

def extract_lifeline(element):
    """
    Extracts a SysML lifeline from an XMI element.

    Args:
        element (Element): The XML element representing the lifeline.

    Returns:
        lifeline (dict): A dictionary representing the SysML lifeline in Json-SysML format.
    """
    lifeline = {
        "name": element.get("name"),
        "id": get_attribute_with_ns("id", element),
    }
    if element.get("represents"):
        represented_element = find_element_by_id(
            element.get("represents"),
            element.getparent()
        )
        lifeline["represents"] = {
            "name": represented_element.get("name"),
            "idref": element.get("represents"),
            "type": get_type(represented_element),
        }

    lifeline = finalize_extraction(element, lifeline)
    return lifeline

def extract_message(element):
    """
    Extracts a SysML message from an XMI element.

    Args:
        element (Element): The XML element representing the message.

    Returns:
        message (dict): A dictionary representing the SysML message in Json-SysML format.
    """
    message = {
        "name": element.get("name"),
        "id": get_attribute_with_ns("id", element)
    }

    root = element.getparent()

    if element.get("messageSort"):
        message["messageSort"] = element.get("messageSort")

    for key, xmi_key in [("source", "sendEvent"), ("target", "receiveEvent")]:
        key_element = None
        if element.get(xmi_key):
            key_element = find_element_by_id(element.get(xmi_key), root)
        if key_element is not None:
            if key_element.tag.endswith("Gate"):
                message[key] = {
                    "name": key_element.tag,
                    "gateOwner": {
                        "name": key_element.getparent().get("name"),
                        "idref": get_attribute_with_ns("id", key_element.getparent())
                    }
                }
            else:
                covered = key_element.find("./covered")
                if covered is not None:
                    lifeline_id = get_attribute_with_ns("idref", covered)
                    lifeline = find_element_by_id(lifeline_id, root)
                    key_name = extract_lifeline(lifeline).get("represents", {}).get("name", "")
                    message[key] = {
                        "name": key_name,
                        "idref": lifeline_id
                    }

    if element.get("signature"):
        signature_element = find_element_by_id(element.get("signature"), root)
        message["signature"] = {
            "name": signature_element.get("name"),
            "idref": element.get("signature")
        }

    if element.xpath("./argument"):
        for argument in element.xpath("./argument"):
            arg = {
                "name": argument.get("name")
            }
            if argument.get("value"):
                arg["value"] = smart_cast(argument.get("value"))
            elif argument.xpath("./body"):
                arg["value"] = {
                    "body": argument.xpath("./body")[0].text.strip()
                }
                if argument.xpath("./language"):
                    arg["value"]["language"] = smart_cast(argument.xpath("./language")[0].text.strip())
            message.setdefault("arguments", []).append(arg)

    message = finalize_extraction(element, message)
    return message

def extract_fragment(element):
    """
    Extracts a SysML interaction fragment from an XMI element.

    Args:
        element (Element): The XML element representing the interaction fragment.

    Returns:
        fragment (dict): A dictionary representing the SysML interaction fragment in Json-SysML format
    """
    xmi_type = get_attribute_with_ns("type", element)
    fragment = {
        "name": element.get("name"),
        "id": get_attribute_with_ns("id", element),
        "fragmentType": xmi_type.split(":")[-1]
    }

    covered_lifelines = [get_attribute_with_ns("idref", covered) for covered in element.findall("./covered")]
    if covered_lifelines:
        fragment["coveredLifelines"] = covered_lifelines

    if element.get("refersTo"):
        referred_element = find_element_by_id(
            element.get("refersTo"),
            element.getparent(),
            {}
        )
        fragment["refersTo"] = {
            "name": referred_element.get("name"),
            "idref": element.get("refersTo")
        }

    if element.get("interactionOperator"):
        fragment["interactionOperator"] = element.get("interactionOperator")

    if element.xpath("./operand"):
        for operand_element in element.xpath("./operand"):
            fragment.setdefault("operands", []).append(extract_operand(operand_element))

    invariant = element.find("./invariant")
    if invariant is not None:
        fragment["invariant"] = {"name": invariant.get("name", ""), "id": get_attribute_with_ns("id", invariant)}
        specification = element.find(".//specification")
        if specification is not None:
            fragment["invariant"]["state"] = {
                "name": find_element_by_id(
                    specification.get("element"),
                    element.getparent(),
                    {}
                ).get("name", ""),
                "idref": specification.get("element")
            }

    fragment = finalize_extraction(element, fragment)
    return fragment

def extract_operand(element):
    """
    Extracts a SysML interaction operand from an XMI element.

    Args:
        element (Element): The XML element representing the interaction operand.

    Returns:
        operand (dict): A dictionary representing the SysML interaction operand in Json-SysML format
    """
    operand = {
        "name": element.get("name"),
        "id": get_attribute_with_ns("id", element),
    }

    if element.xpath("./guard"):
        guard_element = element.xpath("./guard")[0]
        specification = guard_element.xpath("./specification")[0]
        specification_type = get_attribute_with_ns("type", specification)
        if specification_type == "uml:LiteralString":
            operand["guard"] = specification.get("value")
        elif specification_type == "uml:OpaqueExpression":
            body = specification.xpath("./body")
            language = specification.xpath("./language")
            if body or language:
                operand["guard"] = {
                    "body": body[0].text.strip() if body else "",
                    "language": language[0].text.strip() if language else ""
                }

    operand = finalize_extraction(element, operand)
    return operand

def extract_constraint(element):
    """
    Extracts a SysML duration constraint from an XMI element.

    Args:
        element (Element): The XML element representing the duration constraint.

    Returns:
        constraint (dict): A dictionary representing the SysML duration constraint in Json-SysML format
    """
    constraint = {
        "name": element.get("name"),
        "id": get_attribute_with_ns("id", element),
        "type": get_attribute_with_ns("type", element).split(":")[-1]
    }

    constrained_elements = element.xpath("./constrainedElement")
    if len(constrained_elements) == 2:
        for i, constrained_element in enumerate(constrained_elements):
            element_id = get_attribute_with_ns("idref", constrained_element)
            constrained_element_i = {
                "name": find_element_by_id(
                    element_id,
                    element.getparent(),
                    {}
                ).get("name"),
                "idref": element_id
            }
            first_event = element.xpath("./firstEvent")[i].text.strip() if element.xpath("./firstEvent") else ""
            if first_event:
                constrained_element_i["firstEvent"] = first_event == "true"
            constraint.setdefault("constrainedElements", []).append(constrained_element_i)
    elif len(constrained_elements) == 1:
        element_id = get_attribute_with_ns("idref", constrained_elements[0])
        constraint.setdefault("constrainedElements", []).append({
            "name": find_element_by_id(
                element_id,
                element.getparent(),
                {}
            ).get("name"),
            "idref": element_id
        })
        first_event = element.get("firstEvent", "true")
        constraint["constrainedElements"][0]["firstEvent"] = first_event == "true"

    if element.xpath("./specification"):
        specification = element.xpath("./specification")[0]
        for key in ["min", "max"]:
            key_element, expr = None, {}
            key_element = find_element_by_id(
                specification.get(key),
                element.getparent()
            )
            if key_element is not None and key_element.xpath("./expr"):
                expr = key_element.xpath("./expr")[0]
            if expr.get("value"):
                constraint[key] = expr.get("value")

    constraint = finalize_extraction(element, constraint)
    return constraint