
from utils.helpers import namespaces
from utils.getter_utils import find_element_by_id, get_attribute_with_ns
from utils.common_utils import create_sub_element

from lxml import etree

def move_nested_elements(parent_md_elem, nested_element_ids, id_to_md_element_id, diagram_md_owned_views, move_under="mdOwnedViews"):
    move_under_elem = parent_md_elem.find(move_under)
    if move_under_elem is None:
        move_under_elem = create_sub_element(parent_md_elem, move_under)
    for nested_id in nested_element_ids:
        if nested_id not in id_to_md_element_id:
            continue
        idx = 0
        parent_elementID = parent_md_elem.find("elementID")
        if parent_elementID is not None:
            parent_idref = get_attribute_with_ns("idref", parent_elementID)
            if parent_idref is not None and parent_idref in id_to_md_element_id[nested_id]:
                idx = parent_idref
        nested_md_element_id = id_to_md_element_id[nested_id][idx]
        nested_md_element = find_element_by_id(nested_md_element_id, diagram_md_owned_views)
        if nested_md_element is not None:
            move_under_elem.append(nested_md_element)
            if nested_md_element.get("elementClass") == "ObjectNode":
                create_sub_element(nested_md_element, "edge", attrib={
                    etree.QName(namespaces["xmi"], "value"): "3"
                })

def set_md_element_properties(md_element, properties_list):
    properties = md_element.find("properties")
    if properties is None:
        properties = create_sub_element(md_element, "properties")
            
    for prop in properties_list:
        prop_ID = prop.get("propertyID")
        value = prop.get("value")
        element_class = prop.get("elementClass", "ChoiceProperty")

        prop_nodes = properties.xpath(f"./mdElement[@elementClass='{element_class}']/propertyID[text()='{prop_ID}']")
        prop_node = prop_nodes[0] if prop_nodes else None
        if prop_node is None:
            prop_node = create_sub_element(properties, "mdElement", attrib={
                "elementClass": element_class
            })
            create_sub_element(prop_node, "propertyID").text = prop_ID
            if element_class == "ChoiceProperty":
                create_sub_element(prop_node, "index", attrib={
                    etree.QName(namespaces["xmi"], "value"): value
                })
            else:
                create_sub_element(prop_node, "value", attrib={
                    etree.QName(namespaces["xmi"], "value"): value
                })