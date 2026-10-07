
from utils.helpers import smart_cast, all_ns
from utils.getter_utils import (
    find_element_by_id,
    get_attribute_with_ns,
    get_flow_property_direction,
    get_feature_direction,
    get_element_stereotypes,
    get_multiplicity,
    get_body_and_language,
    get_type,
    find_root_model
)
from utils.post_processing import finalize_extraction

def extract_property(element, include_ports=False, diagram_elements_ids=None, include_initial_values=True):
    """
    Extracts a SysML property from an XMI element, including its kind (part, value, reference, constraint, port).

    Args:
        element (Element): The XML element representing the property.
        include_ports (bool): Whether to include ports in the extraction.
        diagram_elements_ids (list): List of IDs of elements in the diagram, used to look up the ports attached to the property.
        include_initial_values (bool): Whether to include initial values.

    Returns:
        dict: A dictionary containing the property information.
    """
    root = element.getparent()
    id = get_attribute_with_ns("id", element)
    name = element.get("name")
    stereotypes = get_element_stereotypes(element)
    property_info = {
        "name": name,
        "id": id,
        "stereotypes": stereotypes,
        "type": get_type(element),
        "multiplicity": get_multiplicity(element)
    }

    type_element = None
    if element.get("type"):
        type_element = find_element_by_id(element.get("type"), root)
        if type_element.xpath("./ownedRule"):
            rules = []
            for rule_element in type_element.findall("ownedRule"):
                try:
                    rule = {
                        "name": rule_element.get("name"),
                        "id": get_attribute_with_ns("id", rule_element),
                    }
                    spec = get_body_and_language(rule_element, "specification")
                    if spec:
                        rule["expression"] = spec
                    rules.append(rule)
                except (IndexError, AttributeError):
                    pass
            property_info.update({"constraints": rules})
    
    if "FlowProperty" in stereotypes:
        direction = get_flow_property_direction(element)
        if direction == "":
            direction = get_feature_direction(element)
        property_info["direction"] = direction

    # Include default value if it exists
    try:
        default_value = element.find("defaultValue").get("value")
        default_value = smart_cast(default_value)
        property_info.update({"defaultValue": default_value})
    except (TypeError, IndexError, AttributeError):
        pass

    # Include owned ports if requested
    if include_ports and diagram_elements_ids and type_element is not None:
        ports = []
        for attribute in type_element.findall("ownedAttribute"):
            if get_attribute_with_ns("type", attribute) == "uml:Port":
                port_id = get_attribute_with_ns("id", attribute)
                if port_id in diagram_elements_ids:
                    ports.append(port_id)
        if ports:
            property_info["ports"] = ports

    # Include initial values if they exist
    if include_initial_values and element.xpath("./defaultValue"):
        default_value_elem = element.xpath("./defaultValue")[0]
        default_value = default_value_elem.get("value")
        if default_value is None:
            try:
                dv_instance = find_element_by_id(default_value_elem.get("instance"), root)
                slots = dv_instance.xpath("./slot")
                for slot in slots:
                    defining_feature = None
                    def_feature = {}
                    if slot.get("definingFeature"):
                        defining_feature = find_element_by_id(slot.get("definingFeature"), root)
                        def_feature = {
                            "name": defining_feature.get("name"),
                            "idref": slot.get("definingFeature"),
                            "type": get_type(defining_feature)
                        }
                    slot_value = slot.get("value")
                    if slot_value is None:
                        try:
                            slot_value = slot.find("value").get("value")
                        except (TypeError, IndexError, AttributeError):
                            slot_value = None
                    if slot_value:
                        property_info.setdefault("initialValues", []).append(
                            {
                                "definingFeature": def_feature,
                                "value": smart_cast(slot_value),
                            }
                        )
            except (TypeError, IndexError, AttributeError):
                pass

    property_info = finalize_extraction(element, property_info)
    return property_info

def extract_port(element):
    """
    Extracts a SysML port from an XMI element.

    Args:
        element (Element): The XML element representing the port.

    Returns:
        dict: A dictionary containing the port information.
    """
    root = element.getroottree().getroot()
    id = get_attribute_with_ns("id", element)
    direction = ""
    try:
        direction = root.xpath(f"./*[@base_Port='{id}']")[0].get("direction")
    except (IndexError, AttributeError):
        pass
    port = {
        "name": element.get("name"),
        "id": id,
        "stereotypes": get_element_stereotypes(element),
        "direction": direction,
        "type": get_type(element),
        "multiplicity": get_multiplicity(element)
    }
    # Include provided/required interfaces if they exist
    provided_interfaces = []
    required_interfaces = []
    if element.get("type"):
        type_id = element.get("type")
        xpaths_to_extract = {
            "providedInterfaces": {
                "xpath": f"//interfaceRealization[client/@xmi:idref='{type_id}']",
                "list": provided_interfaces
            },
            "requiredInterfaces": {
                "xpath": f"//packagedElement[@xmi:type='uml:Usage'][client/@xmi:idref='{type_id}']",
                "list": required_interfaces
            }
        }
        for key, value in xpaths_to_extract.items():
            xpath = value["xpath"]
            interface_list = value["list"]
            for ns in all_ns:
                contracts = find_root_model(root).xpath(xpath, namespaces=ns)
                if contracts:
                    for contract in contracts:
                        supplier_id = get_attribute_with_ns("idref", contract.xpath("./supplier")[0])
                        interface = find_element_by_id(supplier_id, element.getparent())
                        if interface is not None:
                            interface_list.append({
                                "name": interface.get("name"),
                                "idref": supplier_id
                            })
                    break
            if interface_list:
                port[key] = interface_list

    port = finalize_extraction(element, port)
    return port

def extract_connector(element):
    """
    Extracts a SysML connector from an XMI element.

    Args:
        element (Element): The XML element representing the connector.

    Returns:
        dict: A dictionary containing the connector information.
    """
    id = get_attribute_with_ns("id", element)
    name = element.get("name")
    stereotypes = get_element_stereotypes(element)
    ends = []
    for end_elem in element.findall("end"):
        end = {
            "name": find_element_by_id(end_elem.get("role"), element.getparent(), {}).get("name", ""),
            "idref": end_elem.get("role")
        }
        if end_elem.get("partWithPort"):
            end["name"] = find_element_by_id(
                end_elem.get("partWithPort"),
                element.getparent(), {}
            ).get("name", "") + "::" + end["name"]
            end["portOwnerIdref"] = end_elem.get("partWithPort")
        multiplicity = get_multiplicity(end_elem)
        if multiplicity:
            end["multiplicity"] = multiplicity
        ends.append(end)

    # Include item flows if they exist
    item_flows = []
    for ns in all_ns:
        item_flow_elements = find_root_model(element.getroottree().getroot()).xpath(
            f".//packagedElement[@xmi:type='uml:InformationFlow'][realizingConnector/@xmi:idref='{id}']",
            namespaces=ns
        )
        if item_flow_elements:
            for item_flow_element in item_flow_elements:
                item_flows.append(extract_item_flow(item_flow_element))
            break

    connector = {
        "name": name,
        "id": id,
        "stereotypes": stereotypes,
        "ends": ends,
        "itemFlows": item_flows
    }

    connector = finalize_extraction(element, connector)
    return connector

def extract_item_flow(element):
    """
    Extracts a SysML item flow from an XMI element.

    Args:
        element (Element): The XML element representing the item flow.

    Returns:
        dict: A dictionary containing the item flow information.
    """
    id = get_attribute_with_ns("id", element)
    name = element.get("name")

    item_flow = {
        "name": name,
        "id": id
    }

    inner_elements = {
        "conveyed": "./conveyed",
        "sourceIdref": "./informationSource",
        "targetIdref": "./informationTarget",
        # "connectorIdref": "./realizingConnector",
    }
    for key, xpath in inner_elements.items():
        if element.xpath(xpath):
            element_id = get_attribute_with_ns("idref", element.xpath(xpath)[0])
            if key == "conveyed":
                element_item = find_element_by_id(element_id, element.getparent())
                item_flow[key] = {
                    "name": element_item.get("name"),
                    "idref": element_id
                }
            else:
                item_flow[key] = element_id

    root = element.getroottree().getroot()
    stereo_element = root.xpath(f"./*[@base_InformationFlow='{id}']")
    if stereo_element and stereo_element[0].get("itemProperty"):
        item_property = find_element_by_id(stereo_element[0].get("itemProperty"), element.getparent())
        item_flow["itemProperty"] = {
            "name": item_property.get("name"),
            "id": stereo_element[0].get("itemProperty")
        }

    item_flow = finalize_extraction(element, item_flow)
    return item_flow

def check_if_shortcut_property(property, diagram_id, parent):
    """
    Checks if a property is a shortcut (i.e., it is a nested property but it is represented without nesting).

    Args:
        property (dict): The property information extracted from the element.
        diagram_id (str): The ID of the diagram being processed.
        parent (Element): The parent element.

    Returns:
        dict: The original property information if it is not a shortcut, or a modified version indicating it is a shortcut if it is.
    """
    property_id = property.get("id")
    if property_id is None:
        return property
    
    root = parent.getroottree().getroot()
    for ns in all_ns:
        results = root.xpath(f"./xmi:Extension/filePart/mdOwnedViews/mdElement[@elementClass='DiagramFrame'][elementID/@xmi:idref='{diagram_id}']", namespaces=ns)
        if results:
            diagram_md_element = results[0]
            break
    else:
        return property
    
    diagram_md_owned_views = diagram_md_element.getparent()
    for ns in all_ns:
        results = diagram_md_owned_views.xpath(f".//mdElement[@elementClass='Part'][elementID/@xmi:idref='{property_id}']", namespaces=ns)
        if results:
            property_md_element = results[0]
            break
    else:
        return property
    
    nested_parts = property_md_element.find("nestedParts")
    if nested_parts is not None:
        property_path = get_attribute_with_ns("value", nested_parts)
        if property_path:
            shortcut_path = []
            for idref in property_path.split("^"):
                property_elem = find_element_by_id(idref, parent)
                if property_elem is None:
                    return property
                property_info = {
                    "name": property_elem.get("name"),
                    "idref": idref,
                }
                property_type = get_type(property_elem)
                if property_type:
                    property_info["type"] = property_type
                shortcut_path.append(property_info)
            property["shortcutPath"] = shortcut_path
    return property

def structure_nested_properties(diagram, root):
    """
    Structures nested properties in the diagram by checking the filePart and nesting them accordingly.

    Args:
        diagram (dict): The diagram information extracted from the element.
        root (Element): The root element of the XML tree.

    Returns:
        dict: The modified diagram information with nested properties structured.
    """
    diagram_id = diagram.get("id")
    diagram_md_element = None
    for ns in all_ns:
        results = root.xpath(f"./xmi:Extension/filePart/mdOwnedViews/mdElement[@elementClass='DiagramFrame'][elementID/@xmi:idref='{diagram_id}']", namespaces=ns)
        if results:
            diagram_md_element = results[0]
            break
    if diagram_md_element is None:
        return diagram
    
    nested_properties = {}
    diagram_md_owned_views = diagram_md_element.getparent()

    def process_parts(parts, parent_id=None):
        for part_elem in parts.findall("./mdElement[@elementClass='Part']"):
            part_id = get_attribute_with_ns("idref", part_elem.find("elementID"))
            if parent_id:
                nested_properties.setdefault(parent_id, []).append(part_id)
            nested_parts = part_elem.find("parts")
            if nested_parts is not None:
                process_parts(nested_parts, parent_id=part_id)

    process_parts(diagram_md_owned_views)

    # Nesting
    all_properties = {p["id"]: p for p in diagram.get("properties", []) if "id" in p}
    for prop in diagram.get("properties", [])[:]:
        prop_id = prop.get("id")
        if not prop_id:
            continue
        for nested_id in nested_properties.get(prop_id, []):
            nested_prop = all_properties.get(nested_id)
            if nested_prop:
                prop.setdefault("nestedProperties", []).append(nested_prop)
                if nested_prop in diagram["properties"]:
                    diagram["properties"].remove(nested_prop)

    return diagram