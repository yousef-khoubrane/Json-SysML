
from utils.helpers import namespaces, gen_id
from utils.getter_utils import (
    find_element_by_id,
    find_root_model,
)
from utils.common_utils import (
    create_sub_element,
    create_boolean_values,
    create_stereotypes,
)

from lxml import etree

def create_requirement(requirement, parent_elem):
    model_elem = find_root_model(parent_elem.getroottree().getroot())
    if "id" not in requirement:
        requirement["id"] = gen_id()
    req_id = requirement["id"]

    req_elem = find_element_by_id(req_id, parent_elem, top_node=model_elem)
    if req_elem is None:
        req_elem = create_sub_element(parent_elem, "packagedElement", attrib={
            etree.QName(namespaces["xmi"], "type"): "uml:Class",
            etree.QName(namespaces["xmi"], "id"): req_id,
            "name": requirement.get("name", "")
        })
    elif requirement.get("name"):
        req_elem.set("name", requirement.get("name"))

    create_boolean_values(requirement, req_elem)

    create_stereotypes(
        req_id,
        requirement.get("stereotypes", []),
        req_elem.getroottree().getroot(),
        tagged_values=requirement.get("taggedValues", {})
    )

    return req_elem