
from utils.helpers import namespaces, gen_id
from utils.getter_utils import (
    find_element_by_id,
    find_root_model
)
from utils.common_utils import (
    create_sub_element,
    create_boolean_values,
    create_stereotypes,
)

from lxml import etree

def ensure_package_hierarchy(package, root):        
    id_path = package.get("idPath", "model")
    path = package.get("path", "Model")
    id_segments = id_path.split("::")
    name_segments = path.split("::")

    current = find_root_model(root)
    
    for id_seg, name_seg in zip(id_segments[1:], name_segments[1:]):
        found = find_element_by_id(id_seg, current)
            
        if found is None:
            new_id = id_seg if id_seg else gen_id()
            elem = create_sub_element(current, "packagedElement", attrib={
                etree.QName(namespaces["xmi"], "type"): "uml:Package",
                etree.QName(namespaces["xmi"], "id"): new_id,
                "name": name_seg
            })
            current = elem
        else:
            current = found
            
    return current

def create_package(package, root):
    model_elem = find_root_model(root)
    if "id" not in package:
        package["id"] = gen_id()
    pkg_id = package["id"]

    pkg_elem = find_element_by_id(pkg_id, model_elem)
    if pkg_elem is None:
        parent_elem = ensure_package_hierarchy(package.get("owner", {}), root)
        if "name" in package:
            pkg_elem = parent_elem.find(f"./packagedElement[@name='{package['name']}']")
        if pkg_elem is None:
            pkg_elem = create_sub_element(parent_elem, "packagedElement", attrib={
                etree.QName(namespaces["xmi"], "type"): "uml:Package",
                etree.QName(namespaces["xmi"], "id"): pkg_id,
                "name": package.get("name", "")
            })
    
    if package.get("isModel", False):
        pkg_elem.set(etree.QName(namespaces["xmi"], "type"), "uml:Model")
        del package["isModel"]

    create_boolean_values(package, pkg_elem)

    create_stereotypes(
        pkg_id,
        package.get("stereotypes", []),
        root,
    )

    return pkg_elem