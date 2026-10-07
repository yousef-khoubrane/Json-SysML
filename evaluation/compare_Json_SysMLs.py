
import json
import os
import pandas as pd

import argparse
from pathlib import Path

def load_json(filepath):
    """Loads a JSON file from the given filepath."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def calculate_similarity(orig, recon, ignore_keys=None):
    """
    Recursively calculates the ratio of matching elements.
    Returns a tuple: (matched_score, total_possible_score)
    """
    if ignore_keys is None:
        ignore_keys = {"metadata"}
        
    matches = 0.0
    total = 0.0

    if isinstance(orig, dict) and isinstance(recon, dict):
        valid_keys = [k for k in orig.keys() if k not in ignore_keys]
        total += len(valid_keys)
        
        for key in valid_keys:
            if key in recon:
                if isinstance(orig[key], (dict, list)):
                    c_match, c_total = calculate_similarity(orig[key], recon[key], ignore_keys)
                    if c_total > 0:
                        matches += (c_match / c_total)
                else:
                    if orig[key] == recon[key]:
                        matches += 1.0
                        
    elif isinstance(orig, list) and isinstance(recon, list):
        total += len(orig)
        
        if not orig:
            pass 
        elif all(not isinstance(x, (dict, list)) for x in orig):
            recon_copy = list(recon)
            for item in orig:
                if item in recon_copy:
                    matches += 1.0
                    recon_copy.remove(item)
        else:
            match_keys = ["id", "idref", "name", "type"]
            match_key = next((mk for mk in match_keys if isinstance(orig[0], dict) and mk in orig[0]), None)
            
            if match_key:
                recon_dict = {x.get(match_key): x for x in recon if isinstance(x, dict) and match_key in x}
                for item in orig:
                    item_id = item.get(match_key)
                    if item_id in recon_dict:
                        c_match, c_total = calculate_similarity(item, recon_dict[item_id], ignore_keys)
                        if c_total > 0:
                            matches += (c_match / c_total)
            else:
                for i, item in enumerate(orig):
                    if i < len(recon):
                        c_match, c_total = calculate_similarity(item, recon[i], ignore_keys)
                        if c_total > 0:
                            matches += (c_match / c_total)
                            
    else:
        total += 1.0
        if orig == recon:
            matches += 1.0

    return matches, total

def filter_model(model, diagrams_to_skip=[]):
    model["diagrams"] = [
        diagram for diagram in model.get("diagrams", [])
        if diagram.get("diagramType") not in diagrams_to_skip
    ]

def evaluate_json_directories(original_dir, reconstructed_dir, output_csv="evaluation_results.csv", diagrams_to_skip=[]):
    """
    Iterates through paired JSON files in two directories, calculates 
    semantic equivalence, and exports the results to a CSV.
    """
    print(f"Starting batch evaluation...\nOriginal Directory: {original_dir}\nReconstructed Directory: {reconstructed_dir}\n")
    
    results = []
    
    # Iterate through all JSON files in the original directory
    for filename in os.listdir(original_dir):
        if not filename.endswith(".json"):
            continue
            
        orig_path = os.path.join(original_dir, filename)
        recon_path = os.path.join(reconstructed_dir, filename)
        
        # Ensure the paired file exists in the reconstructed directory
        if not os.path.exists(recon_path):
            print(f"Warning: Reconstructed file for {filename} not found. Skipping.")
            continue
            
        orig_data = load_json(orig_path)
        recon_data = load_json(recon_path)

        # Filter out diagrams with diagramType in diagrams_to_skip
        filter_model(orig_data, diagrams_to_skip)
        filter_model(recon_data, diagrams_to_skip)

        # Extract the core semantic payload (the diagrams array)
        orig_diagrams = orig_data.get("diagrams", [])
        recon_diagrams = recon_data.get("diagrams", [])
        
        matches, total = calculate_similarity(orig_diagrams, recon_diagrams)
        
        equivalence_rate = (matches / total) * 100 if total > 0 else 0.0
        
        # Append to our results list
        results.append({
            "Model_Name": filename,
            "Diagram_Count": len(orig_diagrams),
            "Semantic_Equivalence_Rate_Pct": round(equivalence_rate, 2)
        })
        
        print(f"Processed {filename}: {equivalence_rate:.2f}% Equivalence")

    # Convert results to a pandas DataFrame
    df = pd.DataFrame(results)
    df = df.sort_values(by="Diagram_Count", ascending=True).reset_index(drop=True)
    
    # Calculate and append an average/summary row
    if not df.empty:
        avg_rate = df["Semantic_Equivalence_Rate_Pct"].mean()
        print(f"\nBatch Processing Complete. Average Equivalence Rate: {avg_rate:.2f}%")
    
    # Export to CSV
    df.to_csv(output_csv, index=False)
    print(f"Results successfully exported to {output_csv}")
    
    return df

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Evaluate the semantic equivalence between original and reconstructed Json-SysML models."
    )

    parser.add_argument(
        "--original-dir",
        type=Path,
        default=Path("evaluation/data/json-sysml"),
        help="Directory containing the original Json-SysML models. Defaults to 'evaluation/data/json-sysml'."
    )

    parser.add_argument(
        "--reconstructed-dir",
        type=Path,
        default=Path("evaluation/data/reconstructed_json-sysml"),
        help="Directory containing the reconstructed Json-SysML models. Defaults to 'evaluation/data/reconstructed_json-sysml'."
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/results/json_reconstruction_results.csv"),
        help="Output CSV file. Defaults to 'evaluation/results/json_reconstruction_results.csv'."
    )

    parser.add_argument(
        "--skip-diagrams",
        nargs="*",
        default=[],
        metavar="DIAGRAM_TYPE",
        help=(
            "Diagram types to exclude from the comparison. "
            "Provide a space-separated list of diagram types. "
            "For example: --skip-diagrams 'bdd' 'ibd' 'act'"
            "Default is to include all diagram types."
        ),
    )

    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    results_df = evaluate_json_directories(
        original_dir=args.original_dir,
        reconstructed_dir=args.reconstructed_dir,
        output_csv=args.output,
        diagrams_to_skip=args.skip_diagrams,
    )

    print("\nPreview of DataFrame:")
    print(results_df.head())