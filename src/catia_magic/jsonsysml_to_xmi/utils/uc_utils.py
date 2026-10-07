
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

def create_use_case(use_case, parent_elem):
    model_elem = find_root_model(parent_elem.getroottree().getroot())
    if "id" not in use_case:
        use_case["id"] = gen_id()
    use_case_id = use_case["id"]

    use_case_elem = find_element_by_id(use_case_id, parent_elem, top_node=model_elem)
    if use_case_elem is None:
        use_case_elem = create_sub_element(parent_elem, "packagedElement", attrib={
            etree.QName(namespaces["xmi"], "type"): "uml:UseCase",
            etree.QName(namespaces["xmi"], "id"): use_case_id,
            "name": use_case.get("name", "")
        })
    else:
        use_case_elem.set(etree.QName(namespaces["xmi"], "type"), "uml:UseCase")
        if use_case.get("name"):
            use_case_elem.set("name", use_case.get("name"))
        if use_case_elem.getparent() is not parent_elem:
            try:
                parent_elem.append(use_case_elem)
            except Exception:
                pass

    create_boolean_values(use_case, use_case_elem)
    
    create_stereotypes(
        use_case_id,
        use_case.get("stereotypes", []),
        use_case_elem.getroottree().getroot(),
        tagged_values=use_case.get("taggedValues", {})
    )

    return use_case_elem