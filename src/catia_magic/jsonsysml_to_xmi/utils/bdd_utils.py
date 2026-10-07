
from utils.helpers import namespaces, si_definitions, gen_id, smart_uncast
from utils.getter_utils import (
    find_element_by_id,
    find_root_model,
    get_attribute_with_ns,
    get_closest_package,
    get_xmi_type_of_value,
)
from utils.common_utils import (
    create_sub_element,
    create_type,
    create_multiplicity,
    create_boolean_values,
    create_stereotypes,
    remove_stereotypes,
    update_created_nodes,
)

from lxml import etree

def create_class(class_, parent_elem, xmi_type="uml:Class", override_existing=True):
    model_elem = find_root_model(parent_elem.getroottree().getroot())
    if "id" not in class_:
        class_["id"] = gen_id()
    class_id = class_["id"]

    class_elem = find_element_by_id(class_id, parent_elem, top_node=model_elem)
    tag = "packagedElement" if get_attribute_with_ns("type", parent_elem) in ["uml:Package", "uml:Model"] else "nestedClassifier"
    if class_elem is not None:
        if not override_existing:
            return class_elem
        else:
            class_elem.set(etree.QName(namespaces["xmi"], "type"), xmi_type)
            class_elem.set("name", class_.get("name", ""))
        if class_elem is not parent_elem:
            try:
                parent_elem.append(class_elem)
            except Exception:
                pass
            class_elem.tag = tag
            for elem in class_elem:
                if get_attribute_with_ns("type", elem) == "uml:Activity":
                    elem.tag = "ownedBehavior"
                elif elem.tag == "packagedElement":
                    elem.tag = "nestedClassifier"
    else:
        class_elem = create_sub_element(parent_elem, tag, attrib={
            etree.QName(namespaces["xmi"], "type"): xmi_type,
            etree.QName(namespaces["xmi"], "id"): class_id,
            "name": class_.get("name", "")
        })

    create_boolean_values(class_, class_elem)

    stereotypes = class_.get("stereotypes", [])
    if "ConstraintBlock" in stereotypes and "Block" in stereotypes:
        stereotypes.remove("Block")
    create_stereotypes(
        class_id,
        stereotypes,
        class_elem.getroottree().getroot(),
        tagged_values=class_.get("taggedValues", {})
    )

    if xmi_type != "uml:Class":
        remove_stereotypes(class_id, ["Block"], class_elem.getroottree().getroot())

    for prop in class_.get("properties", []):
        create_property(prop, class_elem)

    for op in class_.get("operations", []):
        create_operation(op, class_elem)

    for constraint in class_.get("constraints", []):
        create_constraint(constraint, class_elem)

    for port in class_.get("ports", []):
        create_port(port, class_elem)

    for param in class_.get("parameters", []):
        create_parameter(param, class_elem)

    return class_elem

def create_property(prop, parent_elem, root_model=None):
    if "id" not in prop:
        prop["id"] = gen_id()
    prop_id = prop["id"]
    
    if root_model is not None:
        attr_elem = find_element_by_id(prop_id, parent_elem, top_node=root_model)
    else:
        attr_elem = find_element_by_id(prop_id, parent_elem)

    if attr_elem is None and isinstance(prop.get("type"), dict):
        type_ref = prop.get("type").get("idref")
        type_name = prop.get("type").get("name")
        if type_ref:
            attr_elem_candidate = parent_elem.find(f"./ownedAttribute[@type='{type_ref}']")
            if attr_elem_candidate is not None and attr_elem_candidate.get("name") == type_name:
                attr_elem = attr_elem_candidate
    if attr_elem is not None:
        attr_elem.set(etree.QName(namespaces["xmi"], "type"), "uml:Property")
        old_id = get_attribute_with_ns("id", attr_elem)
        if old_id != prop_id:
            attr_elem.set(etree.QName(namespaces["xmi"], "id"), prop_id)
            update_created_nodes(remove=[old_id], add={prop_id: attr_elem})
        if prop.get("name"):
            attr_elem.set("name", prop.get("name"))
    else:
        prop_attrib = {
            etree.QName(namespaces["xmi"], "type"): "uml:Property",
            etree.QName(namespaces["xmi"], "id"): prop_id,
            "name": prop.get("name", ""),
            "visibility": "public"
        }
        attr_elem = create_sub_element(parent_elem, "ownedAttribute", attrib=prop_attrib)
    
    # Type
    create_type(prop.get("type"), attr_elem, prop.get("stereotypes", []))

    # Aggregation
    stereo = prop.get("stereotypes", [])
    if any(item in stereo for item in ["PartProperty", "ValueProperty", "ConstraintProperty"]):
        attr_elem.set("aggregation", "composite")

    default_value = prop.get("defaultValue")
    if default_value is not None and not attr_elem.xpath("./defaultValue"):
        create_sub_element(attr_elem, "defaultValue", attrib={
            etree.QName(namespaces["xmi"], "type"): get_xmi_type_of_value(prop.get("type", None), default_value),
            etree.QName(namespaces["xmi"], "id"): gen_id(),
            "value": smart_uncast(default_value)
        })
    
    if prop.get("initialValues"):
        model_elem = find_root_model(parent_elem.getroottree().getroot())
        prop_type_elem = find_element_by_id(prop.get("type", {}).get("idref"), parent_elem, top_node=model_elem)
        if prop_type_elem is not None:
            default_value_elem = attr_elem.find("defaultValue")
            instance_id = gen_id()
            if default_value_elem is None:
                default_value_elem = create_sub_element(attr_elem, "defaultValue", attrib={
                    etree.QName(namespaces["xmi"], "type"): "uml:InstanceValue",
                    etree.QName(namespaces["xmi"], "id"): gen_id()
                })
            if not default_value_elem.get("instance"):
                default_value_elem.set("instance", instance_id)
            slots = []
            for val in prop.get("initialValues", []):
                if val.get("definingFeature", {}).get("idref"):
                    create_property(
                        {
                            "id": val.get("definingFeature").get("idref"),
                            **val.get("definingFeature", {}),
                            # "stereotypes": ["ValueProperty"]
                        },
                        prop_type_elem
                    )
                    slots.append({"key": {"idref": val.get("definingFeature").get("idref")}, "value": val.get("value", "")})
            create_instance(
                {
                    "name": prop.get("name", ""),
                    "id": instance_id,
                    "classifier": prop.get("type", {}),
                    "slots": slots,
                },
                get_closest_package(parent_elem)
            )

    create_multiplicity(prop.get("multiplicity"), attr_elem)
    create_boolean_values(prop, attr_elem)
    tagged_values = {"direction": prop.get("direction")} if prop.get("direction") else {}
    create_stereotypes(prop_id, prop.get("stereotypes", []), parent_elem.getroottree().getroot(), tagged_values)

    return attr_elem

def create_operation(op, parent_elem):
    if "id" not in op:
        op["id"] = gen_id()
    op_id = op["id"]

    owned_operation = find_element_by_id(op_id, parent_elem)
    if owned_operation is not None:
        return  # Operation already exists
    
    owned_operation = create_sub_element(parent_elem, "ownedOperation", attrib={
        etree.QName(namespaces["xmi"], "type"): "uml:Operation",
        etree.QName(namespaces["xmi"], "id"): op_id,
        "name": op.get("name", ""),
        "visibility": "public"
    })

    if op.get("featureDirection"):
        tagged_values = {"featureDirection": op.get("featureDirection")}
        create_stereotypes(op_id, ["DirectedFeature"], parent_elem.getroottree().getroot(), tagged_values)

    for param in op.get("parameters", []):
        create_parameter(param, owned_operation)

    create_boolean_values(op, owned_operation)

    create_stereotypes(
        op_id,
        op.get("stereotypes", []),
        parent_elem.getroottree().getroot(),
        tagged_values=op.get("taggedValues", {})
    )

def create_parameter(param, parent_elem, create_activity_parameter_node=False):
    if "id" not in param:
        param["id"] = gen_id()
    param_elem = find_element_by_id(param["id"], parent_elem)
    if param_elem is not None:
        return param_elem
    param_elem = create_sub_element(parent_elem, "ownedParameter", attrib={
        etree.QName(namespaces["xmi"], "type"): "uml:Parameter",
        etree.QName(namespaces["xmi"], "id"): param["id"],
        "name": param.get("name", ""),
        "visibility": "public",
        "direction": param.get("direction", "in"),
    })
    create_type(param.get("type"), param_elem)
    create_boolean_values(param, param_elem)

    if create_activity_parameter_node:
        node = parent_elem.find(f"./node[@parameter='{param['id']}']")
        if node is None:
            create_sub_element(parent_elem, "node", attrib={
                etree.QName(namespaces["xmi"], "type"): "uml:ActivityParameterNode",
                etree.QName(namespaces["xmi"], "id"): f"{param['id']}_node",
                "name": param.get("name", ""),
                "visibility": "public",
                "parameter": param["id"]
            })

    return param_elem

def create_constraint(constraint, parent_elem):
    if "id" not in constraint:
        constraint["id"] = gen_id()
    constraint_id = constraint["id"]
    constraint_elem = find_element_by_id(constraint_id, parent_elem)
    if constraint_elem is not None:
        return  # Constraint already exists
    constraint_elem = create_sub_element(parent_elem, "ownedRule", attrib={
        etree.QName(namespaces["xmi"], "type"): "uml:Constraint",
        etree.QName(namespaces["xmi"], "id"): constraint_id,
        "name": constraint.get("name", "")
    })
    create_sub_element(constraint_elem, "constrainedElement", attrib={
        etree.QName(namespaces["xmi"], "idref"): get_attribute_with_ns("id", parent_elem, fallback="")
    })
    spec_elem = create_sub_element(constraint_elem, "specification", attrib={
        etree.QName(namespaces["xmi"], "type"): "uml:OpaqueExpression",
        etree.QName(namespaces["xmi"], "id"): gen_id(),
    })
    expr = constraint.get("expression", {})
    for key in ["language", "body"]:
        if key in expr:
            create_sub_element(spec_elem, key).text = expr[key]
    create_boolean_values(constraint, constraint_elem)

def create_port(port, parent_elem):
    if "id" not in port:
        port["id"] = gen_id()
    port_id = port["id"]
    port_elem = find_element_by_id(port_id, parent_elem)
    if port_elem is None:
        port_attrib = {
            etree.QName(namespaces["xmi"], "type"): "uml:Port",
            etree.QName(namespaces["xmi"], "id"): port_id,
            "name": port.get("name", ""),
            "visibility": "public",
            "aggregation": "composite"
        }
        port_elem = create_sub_element(parent_elem, "ownedAttribute", attrib=port_attrib)

        create_type(port.get("type"), port_elem)
        create_multiplicity(port.get("multiplicity"), port_elem)
        create_boolean_values(port, port_elem)
        tagged_values = {"direction": port.get("direction")} if port.get("direction") else {}
        create_stereotypes(port_id, port.get("stereotypes", []), parent_elem.getroottree().getroot(), tagged_values)

    # Handle provided/required interfaces
    model_elem = find_root_model(parent_elem.getroottree().getroot())
    type_elem = find_element_by_id(port.get("type", {}).get("idref"), parent_elem, top_node=model_elem)
    if type_elem is None:
        return
    for key in ["providedInterfaces", "requiredInterfaces"]:
        for iface in port.get(key, []):
            iface_idref = iface.get("idref")
            if iface_idref:
                iface_elem = find_element_by_id(iface_idref, parent_elem, top_node=model_elem)
                if iface_elem is None:
                    iface_elem = create_class(
                        {"id": iface_idref, "name": iface.get("name", "")},
                        get_closest_package(parent_elem),
                        xmi_type="uml:Interface"
                    )
                if key == "providedInterfaces":
                    iface_realization = create_sub_element(type_elem, "interfaceRealization", attrib={
                        etree.QName(namespaces["xmi"], "type"): "uml:InterfaceRealization",
                        etree.QName(namespaces["xmi"], "id"): gen_id(),
                        "contract": iface_idref
                    })
                    create_sub_element(iface_realization, "client", attrib={
                        etree.QName(namespaces["xmi"], "idref"): port.get("type").get("idref")
                    })
                    create_sub_element(iface_realization, "supplier", attrib={
                        etree.QName(namespaces["xmi"], "idref"): iface_idref
                    })
                else:
                    iface_usage = create_sub_element(get_closest_package(type_elem), "packagedElement", attrib={
                        etree.QName(namespaces["xmi"], "type"): "uml:Usage",
                        etree.QName(namespaces["xmi"], "id"): gen_id(),
                        "supplier": iface_idref
                    })
                    create_sub_element(iface_usage, "client", attrib={
                        etree.QName(namespaces["xmi"], "idref"): port.get("type").get("idref")
                    })
                    create_sub_element(iface_usage, "supplier", attrib={
                        etree.QName(namespaces["xmi"], "idref"): iface_idref
                    })

def create_instance(instance, parent_elem):
    if "id" not in instance:
        instance["id"] = gen_id()
    instance_id = instance["id"]
    model_elem = find_root_model(parent_elem.getroottree().getroot())
    instance_elem = find_element_by_id(instance_id, parent_elem, top_node=model_elem)
    if instance_elem is None:
        instance_elem = create_sub_element(parent_elem, "packagedElement", attrib={
            etree.QName(namespaces["xmi"], "type"): "uml:InstanceSpecification",
            etree.QName(namespaces["xmi"], "id"): instance_id,
            "name": instance.get("name", "")
        })

    create_instance_classifier(instance.get("classifier"), instance_elem)
    create_boolean_values(instance, instance_elem)
    instance_type = None
    if "QuantityKind" in instance.get("stereotypes", []):
        instance_type = "QuantityKind"
        if "Unit" in instance.get("stereotypes"):
            instance["stereotypes"].remove("Unit")
    elif "Unit" in instance.get("stereotypes", []):
        instance_type = "Unit"
    create_stereotypes(
        instance_id,
        instance.get("stereotypes"),
        instance_elem.getroottree().getroot(),
        tagged_values=instance.get("taggedValues", {})
    )

    for slot in instance.get("slots", []):
        create_slot(slot, instance_elem, instance_type)

    return instance_elem

def create_enumeration(enumeration, parent_elem):
    if "id" not in enumeration:
        enumeration["id"] = gen_id()
    enumeration_id = enumeration["id"]
    model_elem = find_root_model(parent_elem.getroottree().getroot())
    enumeration_elem = find_element_by_id(enumeration_id, parent_elem, top_node=model_elem)
    if enumeration_elem is None:
        enumeration_elem = create_sub_element(parent_elem, "packagedElement", attrib={
            etree.QName(namespaces["xmi"], "type"): "uml:Enumeration",
            etree.QName(namespaces["xmi"], "id"): enumeration_id,
            "name": enumeration.get("name", "")
        })

    create_boolean_values(enumeration, enumeration_elem)
    create_stereotypes(
        enumeration_id,
        enumeration.get("stereotypes"),
        enumeration_elem.getroottree().getroot(),
        tagged_values=enumeration.get("taggedValues", {})
    )

    for literal in enumeration.get("literals", []):
        if "id" not in literal:
            literal["id"] = gen_id()
        literal_id = literal.get("id")
        literal_elem = find_element_by_id(literal_id, enumeration_elem)
        if literal_elem is None:
            literal_elem = create_sub_element(enumeration_elem, "ownedLiteral", attrib={
                # etree.QName(namespaces["xmi"], "type"): "uml:EnumerationLiteral",
                etree.QName(namespaces["xmi"], "id"): literal_id,
                "name": literal.get("name", ""),
                # TODO?: Check when/if literals can have attached values
            })

    return enumeration_elem

def create_instance_classifier(classifier, instance_elem):
    if instance_elem.find("classifier") is not None:
        return  # Classifier already set
    if isinstance(classifier, dict):
        classifier_id = classifier.get("idref")
        if classifier_id:
            classifier_elem = find_element_by_id(
                classifier_id, instance_elem,
                top_node=find_root_model(instance_elem.getroottree().getroot())
            )
            if classifier_elem is None:
                create_class({
                    "name": classifier.get("name", ""),
                    "id": classifier_id
                }, get_closest_package(instance_elem))
            create_sub_element(instance_elem, "classifier", attrib={
                etree.QName(namespaces["xmi"], "idref"): classifier_id
            })
    elif isinstance(classifier, str):
        classifier_hrefs = {
            "DerivedUnit": "QUDV.mdzip#_16_5_1_12c903cb_1245417652468_149854_5164",
            "QuantityKind": "QUDV.mdzip#_16_5_1_12c903cb_1245415169125_739263_4059",
            "QuantityKindFactor": "QUDV.mdzip#_16_5_1_12c903cb_1245416909968_787341_4863",
            "DerivedQuantityKind": "QUDV.mdzip#_16_5_1_12c903cb_1245416800625_456261_4784",
            "Unit": "QUDV.mdzip#_16_5_1_12c903cb_1245417288453_874257_4989",
            "ConversionBasedUnit": "QUDV.mdzip#_16_5_1_12c903cb_1245417567140_403198_5082",
            "AffineConversionUnit": "QUDV.mdzip#_16_5_1_12c903cb_1245417956562_475104_5289"
        }
        if classifier in classifier_hrefs:
            classifier_elem = create_sub_element(instance_elem, "classifier", attrib={
                "href": classifier_hrefs.get(classifier, "")
            })
            xmi_ext = create_sub_element(
                classifier_elem,
                etree.QName(namespaces["xmi"], "Extension"),
                attrib={"extender": "MagicDraw UML 2024x"}
            )
            create_sub_element(xmi_ext, "referenceExtension", attrib={
                "referentPath": f"QUDV::{classifier}",
                "referentType": "Class"
            })

def create_slot(slot, instance_elem, instance_type=None):
    if not slot.get("key") or not slot.get("value"):
        return
    if "id" not in slot:
        slot["id"] = gen_id()
    defining_features = {
        "name": {
            "QuantityKind": ["QuantityKind", "QUDV.mdzip#_16_5_1_12c903cb_1245415215671_546126_4078"],
            "Unit": ["Unit", "QUDV.mdzip#_16_5_1_12c903cb_1245417296734_424943_5008"]
        },
        "factor": {
            "QuantityKind": ["DerivedQuantityKind", "QUDV.mdzip#_16_5_1_12c903cb_1245417043890_594566_4892"],
            "Unit": ["AffineConversionUnit", "QUDV.mdzip#_16_5_1_12c903cb_1245417969468_299264_5308"]
        },
        "quantityKind": {
            "Unit": ["Unit", "QUDV.mdzip#_16_5_1_12c903cb_1245418559312_532344_5543"]
        },
        "symbol": {
            "Unit": ["Unit", "QUDV.mdzip#_16_5_1_12c903cb_1245417296734_435636_5009"]
        },
        "referenceUnit": {
            "Unit": ["ConversionBasedUnit", "QUDV.mdzip#_16_5_1_12c903cb_1245418252656_741269_5421"]
        },
        "isInvertible": {
            "Unit": ["ConversionBasedUnit", "QUDV.mdzip#_16_5_1_12c903cb_1245417580250_653597_5101"]
        },
        "offset": {
            "Unit": ["AffineConversionUnit", "QUDV.mdzip#_16_5_1_12c903cb_1245418010062_864272_5316"]
        }
    }
    slot_elem = create_sub_element(instance_elem, "slot", attrib={
        etree.QName(namespaces["xmi"], "type"): "uml:Slot",
        etree.QName(namespaces["xmi"], "id"): slot["id"]
    })
    if isinstance(slot["key"], str) and slot["key"] in defining_features and instance_type in defining_features[slot["key"]]:
        defining_feature_elem = create_sub_element(slot_elem, "definingFeature", attrib={
            "href": defining_features[slot["key"]][instance_type][1]
        })
        xmi_ext = create_sub_element(
            defining_feature_elem,
            etree.QName(namespaces["xmi"], "Extension"),
            attrib={"extender": "MagicDraw UML 2024x"}
        )
        create_sub_element(xmi_ext, "referenceExtension", attrib={
            "referentPath": f"QUDV::{defining_features[slot['key']][instance_type][0]}::{slot['key']}",
            "referentType": "Property"
        })
    elif isinstance(slot["key"], str):
        slot_elem.set("definingFeature", slot["key"])
    elif isinstance(slot["key"], dict) and slot["key"].get("idref"):
        slot_elem.set("definingFeature", slot["key"]["idref"])
        key_elem = find_element_by_id(
            slot["key"]["idref"], instance_elem,
            top_node=find_root_model(instance_elem.getroottree().getroot())
        )
        if key_elem is None:
            create_class(
                {
                    "name": slot["key"].get("name", ""),
                    "id": slot["key"]["idref"],
                },
                get_closest_package(instance_elem)
            )

    value_elem = create_sub_element(slot_elem, "value", attrib={
        etree.QName(namespaces["xmi"], "type"): get_xmi_type_of_value(None, slot["value"]),
        etree.QName(namespaces["xmi"], "id"): gen_id()
    })
    if isinstance(slot["value"], dict) and slot["value"].get("idref"):
        value_elem.set(etree.QName(namespaces["xmi"], "type"), "uml:InstanceValue")
        value_elem.set("instance", slot["value"]["idref"])
        model_elem = find_root_model(instance_elem.getroottree().getroot())
        referenced_instance = find_element_by_id(slot["value"]["idref"], instance_elem, top_node=model_elem)
        if referenced_instance is None:
            if slot["key"] == "quantityKind":
                create_instance(
                    {
                        "name": slot["value"].get("name", ""),
                        "id": slot["value"]["idref"],
                        "stereotypes": ["QuantityKind"]
                    },
                    instance_elem.getparent()
                )
            elif slot["key"] == "referenceUnit":
                create_instance(
                    {
                        "name": slot["value"].get("name", ""),
                        "id": slot["value"]["idref"],
                        "stereotypes": ["Unit"]
                    },
                    instance_elem.getparent()
                )
            else:
                create_class(
                    {
                        "name": slot["value"].get("name", ""),
                        "id": slot["value"]["idref"],
                    },
                    get_closest_package(instance_elem)
                )
    
    elif isinstance(slot["value"], str) and slot["value"] in si_definitions:
        value_elem.set(etree.QName(namespaces["xmi"], "type"), "uml:InstanceValue")
        instance_elem = create_sub_element(value_elem, "instance", attrib={
            "href": f"http://www.omg.org/spec/SysML/20120401/ISO-80000-1-QUDV.xmi#_ISO-80000-1-QUDV_{slot['value'].replace('^', '_u00255E')}_PackageableElement"
        })
        xmi_ext = create_sub_element(instance_elem, etree.QName(namespaces["xmi"], "Extension"), attrib={
            "extender": "MagicDraw UML 2024x"
        })
        create_sub_element(xmi_ext, "referenceExtension", attrib={
            "referentPath": f"SIDefinitions::{slot['value']}",
            "referentType": "InstanceSpecification",
            "originalID": si_definitions[slot["value"]]
        })
    elif isinstance(slot["value"], str):
        value_elem.set("value", smart_uncast(slot["value"]))