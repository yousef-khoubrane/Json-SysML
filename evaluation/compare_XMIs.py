
import os
import csv
from lxml import etree

import argparse
from pathlib import Path

DIAGRAM_TYPES = {
    "act": "SysML Activity Diagram",
    "bdd": "SysML Block Definition Diagram",
    "ibd": "SysML Internal Block Diagram",
    "par": "SysML Parametric Diagram",
    "pkg": "SysML Package Diagram",
    "req": "Requirement Diagram",
    "sd": "SysML Sequence Diagram",
    "stm": "SysML State Machine Diagram",
    "uc": "SysML Use Case Diagram",
}

def parse_xmi(filepath):
    try:
        tree = etree.parse(filepath)
        root = tree.getroot()
        namespaces = root.nsmap.copy()
        if None in namespaces:
            del namespaces[None]
        return root, namespaces
    except Exception as e:
        print(f"Error parsing XML file {filepath}: {e}")
        return None

def extract_flat_containment(root, namespaces, filtered_ids=[]):
    """Extracts all semantic elements into a flat dictionary by xmi:id."""
    elements = {}
    if root is None:
        return elements
        
    for elem in root.xpath('/xmi:XMI/uml:Model//*[@xmi:id]', namespaces=namespaces):
        xmi_id = elem.get(f"{{{namespaces['xmi']}}}id")
        
        if filtered_ids == [] or (filtered_ids != [] and xmi_id in filtered_ids):
            elements[xmi_id] = elem

    return elements

def extract_diagram_used_elements(root, namespaces, supported_diagrams=None):
    """Extracts diagram IDs and their associated usedElements."""
    diagrams = {}
    if root is None:
        return diagrams
    
    if supported_diagrams is None:
        supported_diagrams = list(DIAGRAM_TYPES.values())
        
    for diagram_node in root.xpath('/xmi:XMI/uml:Model//ownedDiagram', namespaces=namespaces):
        diagram_type = "none"
        try:
            diagram_type = diagram_node[0][0][0].get("type")
        except:
            pass
        if diagram_type not in supported_diagrams:
            continue
        
        diag_id = diagram_node.get(f"{{{namespaces['xmi']}}}id")

        used_elements = []
        for used_el_node in diagram_node.xpath('.//usedElements', namespaces=namespaces):
            if used_el_node.text:
                used_elements.append(used_el_node.text)
                
        diagrams[diag_id] = used_elements
    return diagrams

def compare_nodes(orig_node, recon_node, to_skip=[]):
    """
    Compares two XML nodes including their tags and attributes.
    Returns a similarity score (0.0 to 1.0) based on total matches.
    """    
    if to_skip == []:
        to_skip = ["visibility"]

    if orig_node is None or recon_node is None:
        return 0.0

    matches = 0
    # Start the total count at 1 to account for the tag comparison
    total_features = 1

    # 1. Compare Tags
    if orig_node.tag == recon_node.tag:
        matches += 1

    # 2. Filter and compare attributes
    orig_attrs = {k: v for k, v in orig_node.attrib.items() if k not in to_skip}
    recon_attrs = recon_node.attrib
    
    total_features += len(orig_attrs)

    for attr, value in orig_attrs.items():
        if recon_attrs.get(attr) == value:
            matches += 1

    # Return normalized score
    return float(matches) / total_features

def evaluate_xmi_pair(orig_path, recon_path, model_name, supported_diagrams=None):
    """Evaluates a single pair of XMI files and returns the metrics as a dictionary."""
    orig_root, original_ns = parse_xmi(orig_path)
    recon_root, recon_ns = parse_xmi(recon_path)
    
    if orig_root is None or recon_root is None:
        return None
    
    orig_diagrams = extract_diagram_used_elements(orig_root, original_ns, supported_diagrams)
    total_diagrams = len(orig_diagrams)
    
    # Flatten and deduplicate all used element IDs across all diagrams
    unique_diagram_ids = set()
    for used_ids in orig_diagrams.values():
        unique_diagram_ids.update(used_ids)

    orig_elements = extract_flat_containment(orig_root, original_ns, unique_diagram_ids)
    recon_elements = extract_flat_containment(recon_root, recon_ns, unique_diagram_ids)
        
    total_valid_diagram_elements = 0
    total_diagram_score = 0.0
    diagram_elements_missing = 0
    diagram_elements_mismatch = 0
    
    for used_id in unique_diagram_ids:
        orig_node = orig_elements.get(used_id)
        
        # Skip elements that are missing from the global original tree 
        if orig_node is None:
            continue 
            
        total_valid_diagram_elements += 1
        recon_node = recon_elements.get(used_id)
        
        node_score = compare_nodes(orig_node, recon_node)
        total_diagram_score += node_score
        
        if recon_node is None:
            diagram_elements_missing += 1
        elif node_score < 1.0:
            diagram_elements_mismatch += 1
                
    flat_diagram_fidelity_rate = (total_diagram_score / total_valid_diagram_elements) * 100 if total_valid_diagram_elements > 0 else 100.0

    return {
        "Model_Name": model_name,
        "Diagram_Count": total_diagrams,
        "Unique_Diagram_Elements": total_valid_diagram_elements,
        "Fidelity_Rate": round(flat_diagram_fidelity_rate, 2),
        "Elements_Missing": diagram_elements_missing,
        "Elements_Mismatched": diagram_elements_mismatch,
    }

def batch_evaluate_xmis(originals_dir, reconstructed_dir, output_csv_path, supported_diagrams=None):
    """Iterates over directories, compares matching files, and exports to CSV."""
    results = []
    
    print(f"Starting batch evaluation...\nOriginals: {originals_dir}\nReconstructed: {reconstructed_dir}")
    
    for filename in os.listdir(originals_dir):
        if not filename.endswith(".xmi") and not filename.endswith(".xml"):
            continue
            
        orig_path = os.path.join(originals_dir, filename)
        recon_path = os.path.join(reconstructed_dir, filename)
        
        base_name = os.path.splitext(filename)[0]
        
        if not os.path.exists(recon_path):
            print(f"Skipping {base_name}: Reconstructed file not found.")
            continue
            
        print(f"Evaluating {base_name}...")
        metrics = evaluate_xmi_pair(orig_path, recon_path, base_name, supported_diagrams)
        
        if metrics:
            results.append(metrics)

    if not results:
        print("No valid file pairs found. Exiting.")
        return

    # Export to CSV
    fieldnames = results[0].keys()
    try:
        with open(output_csv_path, mode='w', newline='', encoding='utf-8') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"\nEvaluation complete. Results saved to {output_csv_path}")
    except Exception as e:
        print(f"Error writing to CSV: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Evaluate the fidelity of reconstructed XMI models against the original XMI models."
    )

    parser.add_argument(
        "--original-dir",
        type=Path,
        default=Path("evaluation/data/xmi"),
        help="Directory containing the original XMI models. Defaults to 'evaluation/data/xmi'."
    )

    parser.add_argument(
        "--reconstructed-dir",
        type=Path,
        default=Path("evaluation/data/reconstructed_xmi_original_ids"),
        help=(
            "Directory containing the reconstructed XMI models. "
            "Defaults to 'evaluation/data/reconstructed_xmi_original_ids'."
        )
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/results/xmi_reconstruction_results.csv"),
        help=(
            "Output CSV file. "
            "Defaults to 'evaluation/results/xmi_reconstruction_results.csv'."
        )
    )

    parser.add_argument(
        "--skip-diagrams",
        nargs="*",
        default=[],
        metavar="DIAGRAM_TYPE",
        help=(
            "Diagram types to exclude from the comparison. "
            "Provide a space-separated list of short names "
            "(e.g. bdd ibd act). "
            "Default is to include all supported diagram types."
        ),
    )

    args = parser.parse_args()

    invalid = [
        d for d in args.skip_diagrams
        if d not in DIAGRAM_TYPES.keys()
    ]

    if invalid:
        parser.error(
            f"Unknown diagram type(s): {', '.join(invalid)}. "
            f"Supported types are: {', '.join(DIAGRAM_TYPES.keys())}"
        )

    supported_diagrams = [
        full_name
        for short_name, full_name in DIAGRAM_TYPES.items()
        if short_name not in args.skip_diagrams
    ]

    args.output.parent.mkdir(parents=True, exist_ok=True)

    batch_evaluate_xmis(
        originals_dir=args.original_dir,
        reconstructed_dir=args.reconstructed_dir,
        output_csv_path=args.output,
        supported_diagrams=supported_diagrams,
    )