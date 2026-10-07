
from utils.getter_utils import (
    get_attribute_with_ns,
    get_element_stereotypes,
    get_type
)
from utils.post_processing import finalize_extraction

def extract_requirement(element):
    """
    Extracts a SysML requirement from an XMI element.

    Args:
        element (Element): The XML element representing the requirement.

    Returns:
        dict: A dictionary containing the requirement information.
    """
    id = get_attribute_with_ns("id", element)
    req = {
        "name": element.get("name"),
        "id": id,
    }

    stereotypes, tagged_values = get_element_stereotypes(element, extract_tagged_values=True)
    if tagged_values:
        req["taggedValues"] = tagged_values
    if stereotypes:
        req["stereotypes"] = [stereo for stereo in stereotypes if stereo != "Requirement"]

    req = finalize_extraction(element, req)
    return req

def extract_test_case(element):
    """
    Extracts a SysML test case from an XMI element.

    Args:
        element (Element): The XML element representing the test case.

    Returns:
        dict: A dictionary containing the test case information.
    """
    id = get_attribute_with_ns("id", element)
    test_case = {
        "name": element.get("name"),
        "id": id,
    }

    parameters = []
    for param in element.findall("ownedParameter"):
        param_name = param.get("name")
        param_direction = param.get("direction")
        param_type = get_type(param)
        if param_name != "verdict" or param_direction != "return" or param_type != "VerdictKind":
            parameters.append({
                "name": param_name,
                "direction": param_direction,
                "type": param_type
            })

    if parameters:
        test_case["parameters"] = parameters
    
    test_case = finalize_extraction(element, test_case)
    return test_case
