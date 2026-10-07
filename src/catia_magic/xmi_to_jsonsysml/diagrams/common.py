
from utils.getter_utils import (
    get_attribute_with_ns,
    get_element_stereotypes
)
from utils.common_utils import extract_relationship, extract_comment
from utils.act_utils import extract_activity
from utils.bdd_utils import (
    extract_block,
    extract_enumeration,
    extract_instance
)
from utils.pkg_utils import extract_package
from utils.req_utils import extract_requirement, extract_test_case
from utils.stm_utils import extract_state_machine
from utils.uc_utils import extract_uc_relationship, extract_usecase

def extract_element(diagram, element):
    """
    Extracts a SysML element given its XMI type and updates the provided diagram dictionary.

    Args:
        diagram (dict): The SysML Package Diagram in Json-SysML format.
        element (Element): The XML element to extract information from.

    Returns:
        diagram (dict): The updated SysML Package Diagram with the extracted information.
    """
    xmi_type = get_attribute_with_ns("type", element)
    xsi_type = get_attribute_with_ns("xsi:type", element)
    id = get_attribute_with_ns("id", element)

    type_matches = lambda expected_types: xmi_type in expected_types or xsi_type in expected_types

    if type_matches(["uml:Class"]):
        stereotypes = get_element_stereotypes(element)
        if any(ele.endswith("Requirement") for ele in stereotypes):
            diagram.setdefault("requirements", []).append(extract_requirement(element))
        elif any(ele.endswith("Block") for ele in stereotypes):
            diagram.setdefault("blocks", []).append(extract_block(element))
        else:
            diagram.setdefault("classes", []).append(extract_block(element))
    
    elif type_matches(["uml:AssociationClass"]):
        diagram.setdefault("blocks", []).append(extract_block(element))
        diagram.setdefault("relationships", []).append(extract_relationship(element))

    elif type_matches(["uml:Diagram"]):
        diagram.setdefault("referencedDiagrams", []).append(
            {
                "name": element.get("name"),
                "idref": id
            }
        )

    elif type_matches(["uml:Package", "uml:Model"]) or element.tag.endswith("Package"):
        diagram.setdefault("packages", []).append(extract_package(element))

    elif type_matches(["uml:UseCase"]):
        diagram.setdefault("useCases", []).append(extract_usecase(element))

    elif type_matches(["uml:Actor"]):
        diagram.setdefault("actors", []).append(extract_block(element))

    elif type_matches(["uml:Interface"]):
        extracted = extract_block(element)
        if "stereotypes" in extracted and "FlowSpecification" in extracted["stereotypes"]:
            extracted["stereotypes"].remove("FlowSpecification")
            diagram.setdefault("flowSpecifications", []).append(extracted)
        else:
            diagram.setdefault("interfaces", []).append(extracted)

    elif type_matches(["uml:Signal"]):
        diagram.setdefault("signals", []).append(extract_block(element))

    elif type_matches(["uml:Activity", "uml:Interaction"]):
        stereotypes = get_element_stereotypes(element)
        if "TestCase" in stereotypes:
            diagram.setdefault("testCases", []).append(extract_test_case(element))
        else:
            diagram.setdefault("activities", []).append(extract_activity(element))

    elif type_matches(["uml:Component"]):
        diagram.setdefault("classes", []).append(extract_block(element))

    elif type_matches(["uml:DataType"]):
        diagram.setdefault("dataTypes", []).append(extract_block(element))

    elif type_matches(["uml:Enumeration"]):
        diagram.setdefault("enumerations", []).append(extract_enumeration(element))

    elif type_matches(["uml:InstanceSpecification"]):
        stereotypes = get_element_stereotypes(element)
        if "Unit" in stereotypes or "QuantityKind" in stereotypes:
            unit = extract_instance(element)
            unit["stereotypes"] = [s for s in unit["stereotypes"] if s != "Unit"]
            diagram.setdefault("units", []).append(unit)
        else:
            diagram.setdefault("instanceSpecifications", []).append(extract_instance(element))

    elif type_matches(["uml:StateMachine"]):
        diagram.setdefault("stateMachines", []).append(extract_state_machine(element))

    elif type_matches([
        "uml:Association", "uml:Generalization", "uml:InterfaceRealization",
        "uml:Usage", "uml:InformationFlow", "uml:Dependency", "uml:Abstraction",
        "uml:PackageImport"
    ]):
        diagram.setdefault("relationships", []).append(extract_relationship(element))

    elif type_matches(["uml:Include", "uml:Extend"]):
        diagram.setdefault("relationships", []).append(extract_uc_relationship(element))
        
    elif type_matches(["uml:Comment"]):
        diagram.setdefault("comments", []).append(extract_comment(element))
    
    return diagram