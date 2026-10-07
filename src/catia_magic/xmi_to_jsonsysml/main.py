
from diagrams import (
    extract_act,
    extract_bdd,
    extract_ibd,
    extract_par,
    extract_pkg,
    extract_req,
    extract_sd,
    extract_stm,
    extract_uc,
)
from utils.helpers import namespaces
from utils.getter_utils import get_attribute_with_ns, get_element_stereotypes
from utils.common_utils import extract_containment_relationships
from utils.post_processing import (
    deduplicate_element_definitions,
    remove_empty_fields,
    sort_diagrams,
    sort_diagram_fields,
    clean_strings,
    remap_ids
)

from lxml import etree
import json
from tqdm import tqdm

import argparse
from pathlib import Path
import traceback
import logging

class TqdmLoggingHandler(logging.Handler):
    def emit(self, record):
        msg = self.format(record)
        tqdm.write(msg)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(TqdmLoggingHandler())

extract = {
    "SysML Activity Diagram": extract_act,
    "SysML Block Definition Diagram": extract_bdd,
    "SysML Internal Block Diagram": extract_ibd,
    "SysML Parametric Diagram": extract_par,
    "SysML Package Diagram": extract_pkg,
    "SysML Requirement Diagram": extract_req,
    "SysML Sequence Diagram": extract_sd,
    "SysML State Machine Diagram": extract_stm,
    "SysML Use Case Diagram": extract_uc,
}


def xmi_to_json_sysml(
    xmi_file_path,
    clean_ids=True,
    extract_diagram_metadata=False,
    minify_reused_elements=True
):
    """
    Converts a SysML XMI file (from Catia Magic) to Json-SysML syntax.

    Args:
        xmi_file_path (str): Path to the input XMI file.
        clean_ids (bool): If True, remaps IDs to a human-readable format.
        extract_diagram_metadata (bool): Whether to include diagram tagged values.
        minify_reused_elements (bool): If True, minimizes the definitions of reused elements in multiple diagrams.

    Returns:
        dict: A dictionary representing the SysML model in Json-SysML format.
              Returns None if parsing fails.
    """
    try:

        # Parse the XMI file
        tree = etree.parse(xmi_file_path)
        root = tree.getroot()

        sysml_model_json = {
            "name": "Model",
            "id": "",
            "metadata": {},
            "diagrams": []
            }
        root_model = root.xpath("//uml:Model", namespaces=namespaces)
        if root_model:
            root_model = root_model[0]
        else:
            logger.warning("No root model found in the XMI file.")
            return {}
        
        sysml_model_json["name"] = root_model.get("name", "Model")
        sysml_model_json["id"] = get_attribute_with_ns("id", root_model)
        try:
            project_details = root_model.find("ownedComment").get("body")[:-2].split(".\n")
            project_details = [tuple(line.split(":", maxsplit=1)) for line in project_details]
            project_details = {key: value for key, value in project_details}
            sysml_model_json["metadata"] = {key: value for key, value in project_details.items()}
        except:
            pass

        owned_diagrams = list(root.iter("ownedDiagram"))

        for diagram in tqdm(owned_diagrams):

            diagram_type = diagram[0][0][0].get("type")
            if diagram_type == "Requirement Diagram":
                diagram_type = "SysML " + diagram_type

            if diagram_type in extract:
                # diagram_name = diagram.get("name")
                # logger.info(f"Extracting {diagram_type} '{diagram_name}'...")
                diagram_json = extract[diagram_type](diagram)
                extract_containment_relationships(diagram_json, root)
                if extract_diagram_metadata:
                    _, diagram_tagged_values = get_element_stereotypes(diagram, extract_tagged_values=True)
                    if diagram_tagged_values:
                        diagram_json["taggedValues"] = diagram_tagged_values
                sysml_model_json["diagrams"].append(diagram_json)

        sysml_model_json = remove_empty_fields(sysml_model_json)
        sysml_model_json = clean_strings(sysml_model_json)
        sysml_model_json = sort_diagrams(sysml_model_json)
        sysml_model_json = sort_diagram_fields(sysml_model_json)
        if minify_reused_elements:
            sysml_model_json = deduplicate_element_definitions(sysml_model_json)
        if clean_ids:
            sysml_model_json = remap_ids(sysml_model_json)

        return sysml_model_json

    except etree.XMLSyntaxError:
        logger.error(f"Error parsing XMI file:\n{traceback.format_exc()}")
        return None
    except Exception:
        logger.error(f"An unexpected error occurred:\n{traceback.format_exc()}")
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert a MagicDraw/CATIA Magic SysML XMI model to Json-SysML."
    )

    parser.add_argument(
        "input",
        help="Path to the input XMI file."
    )

    parser.add_argument(
        "output",
        nargs="?",
        help="Output JSON file (defaults to <input>.json)."
    )

    parser.add_argument(
        "--no-clean-ids",
        action="store_true",
        help="Do not remap element IDs to human-readable IDs."
    )

    parser.add_argument(
        "--diagram-metadata",
        action="store_true",
        help="Extract diagram tagged values."
    )

    parser.add_argument(
        "--no-minify",
        action="store_true",
        help="Disable minification of reused element definitions."
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = (
        Path(args.output)
        if args.output
        else input_path.with_suffix(".json")
    )

    if not input_path.exists():
        parser.error(f"Input file does not exist: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Converting '{input_path}' to Json-SysML...")

    converted_model = xmi_to_json_sysml(
        input_path,
        clean_ids=not args.no_clean_ids,
        extract_diagram_metadata=args.diagram_metadata,
        minify_reused_elements=not args.no_minify,
    )

    if converted_model is None:
        logger.error("XMI conversion failed.")
        raise SystemExit(1)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(converted_model, f, indent=2)

    logger.info(f"Conversion successful! Output saved to '{output_path}'")