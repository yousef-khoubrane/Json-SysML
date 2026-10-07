

from diagrams.common import process_diagram

from utils.helpers import parse_json, parse_xmi_template
from utils.getter_utils import (
    find_root_model, get_attribute_with_ns,
    get_element_stereotypes
)
from utils.common_utils import create_stereotypes, replace_model_id, sort_diagrams
from utils.act_utils import create_activity
from utils.bdd_utils import create_class
from utils.pkg_utils import ensure_package_hierarchy
from utils.stm_utils import create_state_machine
import utils.variables as VARIABLES

import argparse
from pathlib import Path
from tqdm import tqdm
import traceback
import logging

class TqdmLoggingHandler(logging.Handler):
    def emit(self, record):
        msg = self.format(record)
        tqdm.write(msg)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(TqdmLoggingHandler())

def json_sysml_to_xmi(
    json_input_path,
    xmi_template_path = "src/catia_magic/jsonsysml_to_xmi/resources/empty_model.xml",
    xmi_output_path = "output/toy_smr_reconstructed.xml"
):
    """
    Converts a Json-SysML model back into an XMI file structure.
    
    Args:
        json_input_path (str): Path to the source JSON file.
        xmi_template_path (str): Path to the base XMI template.
        xmi_output_path (str): Path where the resulting XMI will be saved.
    """
    try:
        # Load and Prepare Data
        model = parse_json(json_input_path)
        tree = parse_xmi_template(xmi_template_path)
        root_model = find_root_model(tree)
        root_model.set("name", model.get("name", "Model"))

        # Replace the model ID in the Json-SysML with the one from the XMI template to ensure consistency
        root_model_id = get_attribute_with_ns("id", root_model)
        model = replace_model_id(model, root_model_id)

        # Sort diagrams for dependency handling (e.g., bdds before ibds)
        model = sort_diagrams(model)

        for diagram in tqdm(model.get("diagrams", []), desc="Processing Diagrams"):

            # diagram_name = diagram.get('name')
            # diagram_type = diagram.get('diagramType', '').upper()
            # logger.info(f"Creating {diagram_type} '{diagram_name}'...")

            owner = diagram.get("owner")
            parent_elem = None

            # Handle Activity Diagram context defaults
            diagram_type = diagram.get("diagramType")
            if diagram_type in ["act", "ibd", "par", "sd", "stm"] and "context" not in diagram:
                diagram["context"] = {
                    "name": owner.get("path", "Model").rsplit("::", 1)[-1],
                    "idref": owner.get("idPath", "model").rsplit("::", 1)[-1]
                }

            # Resolve Context/Parent Element
            context_id = diagram.get("context", {}).get("idref")
            if context_id:
                if context_id == owner.get("idPath", "model").rsplit("::", 1)[-1]:
                    parent_pkg_path = {
                        "path": owner.get("path", "Model").rsplit("::", 1)[0],
                        "idPath": owner.get("idPath", "model").rsplit("::", 1)[0]
                    }
                    parent_pkg_elem = ensure_package_hierarchy(parent_pkg_path, root_model)
                else:
                    parent_pkg_elem = ensure_package_hierarchy(owner, root_model)
                
                context_data = {
                    "name": diagram.get("context").get("name"),
                    "id": context_id,
                }
                    
                if diagram_type == "act":
                    context_elem = create_activity(context_data, parent_pkg_elem)
                elif diagram_type == "stm":
                    context_elem = create_state_machine(context_data, parent_pkg_elem)
                elif diagram_type == "sd":
                    xmi_type = f"uml:{diagram.get('context', {}).get('type', 'Interaction')}"
                    context_data["isReentrant"] = False
                    context_elem = create_activity(context_data, parent_pkg_elem, xmi_type=xmi_type)
                else:
                    context_elem = create_class(context_data, parent_pkg_elem)
                    context_stereotypes = get_element_stereotypes(context_elem)
                    if all(item not in context_stereotypes for item in [
                        "Block", "System", "Domain", "External", "Subsystem", "System_context"
                    ]):
                        create_stereotypes(context_id, ["Block"], tree.getroot())
                
                parent_elem = context_elem

            # Fallback to package hierarchy if no specific context element was assigned
            if parent_elem is None:
                parent_elem = ensure_package_hierarchy(owner, root_model)

            # Generate XMI elements for the specific diagram type
            process_diagram(diagram, parent_elem)

        # Write output
        tree.write(xmi_output_path, pretty_print=True, xml_declaration=True, encoding="UTF-8")
        logger.info(f"XMI model successfully written to {xmi_output_path}")

        if VARIABLES.UNRECOGNIZED_STEREOTYPES:
            logger.warning("The following stereotypes were not recognized and skipped:")
            for s in sorted(VARIABLES.UNRECOGNIZED_STEREOTYPES):
                logger.warning(f"  - {s}")

        # Reset created nodes and unrecognized stereotypes: this is relevant when processing multiple inputs
        VARIABLES.CREATED_NODES = {}
        VARIABLES.UNRECOGNIZED_STEREOTYPES.clear()

        return True

    except Exception:
        logger.error(f"An unexpected error occurred during XMI generation:\n{traceback.format_exc()}")
        return False

if __name__ == "__main__":
    DEFAULT_TEMPLATE = (
        "src/catia_magic/jsonsysml_to_xmi/resources/empty_model.xml"
    )

    parser = argparse.ArgumentParser(
        description="Convert a Json-SysML model to a CATIA Magic/MagicDraw XMI model."
    )

    parser.add_argument(
        "input",
        help="Path to the input Json-SysML file."
    )

    parser.add_argument(
        "output",
        nargs="?",
        help="Output XMI file (defaults to <input>.xml)."
    )

    parser.add_argument(
        "--template",
        default=DEFAULT_TEMPLATE,
        help=f"Path to the XMI template (default: {DEFAULT_TEMPLATE})"
    )

    args = parser.parse_args()

    input_path = Path(args.input)

    if not input_path.exists():
        parser.error(f"Input file does not exist: {input_path}")

    output_path = (
        Path(args.output)
        if args.output
        else input_path.with_suffix(".xml")
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Starting conversion: {input_path} -> {output_path}")

    success = json_sysml_to_xmi(
        json_input_path=input_path,
        xmi_template_path=args.template,
        xmi_output_path=output_path,
    )

    if not success:
        raise SystemExit(1)