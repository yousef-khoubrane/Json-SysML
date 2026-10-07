
import os
import json
import pandas as pd
import xml.etree.ElementTree as ET
import tiktoken

import argparse
from pathlib import Path

def load_tokenizer():
    """Loads the tiktoken tokenizer once to avoid loop overhead."""
    print("Loading tiktoken tokenizer into memory...")
    return tiktoken.get_encoding("cl100k_base")

def get_token_count(text, tiktoken_enc):
    """Calculates the tiktoken token count for a given text string."""
    return len(tiktoken_enc.encode(text))

def calculate_reduction_pct(smaller, larger):
    """Calculates the percentage reduction."""
    return (1 - (smaller / larger)) * 100 if larger > 0 else 0.0

def evaluate_compression_directories(xmi_dir, json_dir, output_csv="compression_results.csv"):
    """
    Iterates through paired XMI and JSON files (both standard and minified),
    calculates character and token compression metrics, and exports to a CSV.
    """
    tiktoken_enc = load_tokenizer()
    results = []
    
    print(f"\nStarting batch compression evaluation...\nXMI Directory: {xmi_dir}\nJSON Directory: {json_dir}\n")
    
    for filename in os.listdir(json_dir):
        # Skip files that are not JSON
        if not filename.endswith(".json"):
            continue
            
        base_name = os.path.splitext(filename)[0]
        json_path = os.path.join(json_dir, filename)
        
        # Try to find the matching XMI file
        xmi_path = os.path.join(xmi_dir, f"{base_name}.xml")        
        if not os.path.exists(xmi_path):
            print(f"Warning: Corresponding XMI for {filename} not found. Skipping.")
            continue
            
        # Parse Standard JSON
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                json_data = json.load(f)
            json_str = json.dumps(json_data, indent=2) # Enforce standard formatting for baseline
        except Exception as e:
            print(f"Error reading JSON {filename}: {e}")
            continue

        # Generate No-Indent JSON
        try:
            json_ni_str = json.dumps(json_data, indent=None, separators=(', ', ': '))
        except Exception as e:
            print(f"Error generating minified JSON for {base_name}: {e}")
            continue
            
        # Parse XMI
        try:
            with open(xmi_path, "r", encoding="utf-8") as f:
                xml_content = f.read()
            root = ET.fromstring(xml_content)
            xmi_str = ET.tostring(root, encoding="unicode")
        except Exception as e:
            print(f"Error reading XMI for {base_name}: {e}")
            continue

        # Calculate the number of diagrams in the model
        n_diagrams = len(json_data.get("diagrams", []))
            
        # Calculate Character Lengths
        json_len = len(json_str)
        json_ni_len = len(json_ni_str)
        xmi_len = len(xmi_str)
        
        # Calculate Token Counts
        json_tokens_tik = get_token_count(json_str, tiktoken_enc)
        json_ni_tokens_tik = get_token_count(json_ni_str, tiktoken_enc)
        xmi_tokens_tik = get_token_count(xmi_str, tiktoken_enc)
        
        # Calculate Reductions (Standard JSON vs XMI)
        char_reduction = calculate_reduction_pct(json_len, xmi_len)
        tik_reduction = calculate_reduction_pct(json_tokens_tik, xmi_tokens_tik)

        # Calculate Reductions (Minified JSON vs XMI)
        char_reduction_ni = calculate_reduction_pct(json_ni_len, xmi_len)
        tik_reduction_ni = calculate_reduction_pct(json_ni_tokens_tik, xmi_tokens_tik)
        
        results.append({
            "Model_Name": base_name,
            "Diagram_Count": n_diagrams,
            "XMI_Characters": xmi_len,
            "JSON_Characters": json_len,
            "JSON_NoIndent_Characters": json_ni_len,
            "Char_Reduction_Pct": round(char_reduction, 2),
            "Char_Reduction_NoIndent_Pct": round(char_reduction_ni, 2),

            "XMI_Tokens_Tiktoken": xmi_tokens_tik,
            "JSON_Tokens_Tiktoken": json_tokens_tik,
            "JSON_NoIndent_Tokens_Tiktoken": json_ni_tokens_tik,
            "Tiktoken_Reduction_Pct": round(tik_reduction, 2),
            "Tiktoken_Reduction_NoIndent_Pct": round(tik_reduction_ni, 2)
        })
        
        print(f"Processed {base_name}:")
        print(f"  Standard JSON: {tik_reduction:.2f}% Token Reduction (tiktoken)")
        print(f"  Minified JSON: {tik_reduction_ni:.2f}% Token Reduction (tiktoken)")

    # Structure and export data
    df = pd.DataFrame(results)
    df = df.sort_values(by="Diagram_Count", ascending=True).reset_index(drop=True)
    
    if not df.empty:
        avg_char_red = df["Char_Reduction_Pct"].mean()
        avg_char_red_ni = df["Char_Reduction_NoIndent_Pct"].mean()
        avg_tik_red = df["Tiktoken_Reduction_Pct"].mean()
        avg_tik_red_ni = df["Tiktoken_Reduction_NoIndent_Pct"].mean()
        
        print(f"\nBatch Processing Complete.")
        print(f"Average Character Reduction (Standard): {avg_char_red:.2f}%")
        print(f"Average Character Reduction (Minified): {avg_char_red_ni:.2f}%")
        print(f"Average Token Reduction (tiktoken, Standard): {avg_tik_red:.2f}%")
        print(f"Average Token Reduction (tiktoken, Minified): {avg_tik_red_ni:.2f}%")
        
    df.to_csv(output_csv, index=False)
    print(f"Results successfully exported to {output_csv}")
    
    return df

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Evaluate the character and tiktoken token compression achieved by Json-SysML compared to XMI."
    )

    parser.add_argument(
        "--xmi-dir",
        type=Path,
        default=Path("evaluation/data/xmi"),
        help="Directory containing the reference XMI models. Defaults to 'evaluation/data/xmi'."
    )

    parser.add_argument(
        "--json-dir",
        type=Path,
        default=Path("evaluation/data/json-sysml"),
        help="Directory containing the Json-SysML models. Defaults to 'evaluation/data/json-sysml'."
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/results/compression_efficiency_results.csv"),
        help="Output CSV file. Defaults to 'evaluation/results/compression_efficiency_results.csv'."
    )

    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    results_df = evaluate_compression_directories(
        xmi_dir=args.xmi_dir,
        json_dir=args.json_dir,
        output_csv=args.output,
    )

    print("\nPreview of DataFrame:")
    print(results_df.head())