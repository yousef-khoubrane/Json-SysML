
import os
import traceback
import pandas as pd
from openai import OpenAI
import argparse
from pathlib import Path

def evaluate_model_comprehension(file_path, payload_type, query_params, model_name="deepseek/deepseek-v4-flash"):
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
    )

    with open(file_path, 'r', encoding='utf-8') as file:
        payload = file.read()

    prompt = f"""Please analyze the system model payload provided in the <payload> tags below and answer the following five questions.

Questions:
1. Locate the block named '{query_params['target_block']}'. Extract its unique identifier. List the names of all its owned properties and state their assigned types. If a property is untyped, explicitly state 'Untyped'.
2. Locate the element named '{query_params['stereo_element']}'. List all stereotypes applied to this element. If no stereotypes are applied, output 'None'.
3. Identify all relationships connected to the element named '{query_params['target_element']}'. For each connection, list the name of the connected element, the relationship type, and state whether '{query_params['target_element']}' acts as the source or the target.
4. List the names of all diagrams that visually represent the element named '{query_params['nested_element']}' as a distinct node. Exclude diagrams where '{query_params['nested_element']}' is only referenced as a type for another displayed element.
5. List the names of all elements that are used as shapes within the {query_params['diagram_type']} diagram named '{query_params['diagram_name']}'. Exclude relationships and connectors.

<payload>
{payload}
</payload>"""

    response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "You are an expert systems engineer analyzing structural model data. Be concise and precise."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        # max_completion_tokens=13107,
        # temperature=1.0,
        # top_p=1.0,
        # frequency_penalty=0.0,
        # presence_penalty=0.0,
        extra_body={"reasoning": {"enabled": True}},
        model=model_name
    )

    answer = response.choices[0].message.content
    usage = response.usage
    
    # Return a flat dictionary suitable for a Pandas DataFrame row
    return {
        "file_path": file_path,
        "payload_type": payload_type,
        "query_params": query_params,
        "model_response": answer,
        "prompt_tokens": usage.prompt_tokens if usage else 0,
        "completion_tokens": usage.completion_tokens if usage else 0,
        "total_tokens": usage.total_tokens if usage else 0
    }

def run_batch_evaluation(xmi_paths, query_params_list, output_csv, model_name="deepseek/deepseek-v4-flash"):
    results = []
    
    try:
        for xmi_path, params in zip(xmi_paths, query_params_list):
            json_path = xmi_path.replace("data/xmi/", "data/json-sysml/").replace(".xml", ".json")
            
            print(f"Processing XMI: {xmi_path}")
            xmi_result = evaluate_model_comprehension(xmi_path, "XMI", params, model_name)
            results.append(xmi_result)
            
            print(f"Processing JSON: {json_path}")
            json_result = evaluate_model_comprehension(json_path, "JSON", params, model_name)
            results.append(json_result)
            
    except KeyboardInterrupt:
        print("\nExecution interrupted by user (Ctrl+C). Initiating graceful shutdown.")
    except Exception:
        print(f"\nExecution halted due to error:\n{traceback.format_exc()}")
    finally:
        if results:
            Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
            print(f"Saving {len(results)} processed records to {output_csv}.")
            df = pd.DataFrame(results)
            
            # Append if the file exists, write with header if it is new
            file_exists = os.path.isfile(output_csv)
            df.to_csv(output_csv, mode='a', index=False, header=not file_exists, encoding='utf-8')
        else:
            print("No data processed. Exiting without saving.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate model comprehension on Json-SysML vs XMI payloads via OpenRouter API.")
    parser.add_argument(
        "--model", 
        type=str, 
        default="deepseek/deepseek-v4-flash", 
        help="The model identifier to use via OpenRouter."
    )
    parser.add_argument(
        "--output", 
        type=str, 
        default=None, 
        help="Custom path for the output CSV file."
    )
    
    parser.add_argument(
        "--include-proprietary",
        action="store_true",
        help="Also send the seven CATIA Magic vendor samples to the LLM provider. Requires authorization to share their contents."
    )
    args = parser.parse_args()

    # Define inputs
    xmi_files = [
        "evaluation/data/xmi/PBR-Xref.xml",
        "evaluation/data/xmi/basic units.xml",
        "evaluation/data/xmi/Behavior-to-Structure Synchronization.xml",
        "evaluation/data/xmi/Conjugated Interface Block.xml",
        "evaluation/data/xmi/context specific values.xml",
        "evaluation/data/xmi/contextual relationships.xml",
        "evaluation/data/xmi/Suspect Links.xml",
        "evaluation/data/xmi/WaterSupply.xml",
    ]

    query_params_keys = ["target_block", "stereo_element", "target_element", "nested_element", "diagram_type", "diagram_name"]
    
    params_list = [
        ["System", "R2", "Analysis Context", "System", "IBD", "Analysis"],
        ["Engine", "mass", "System", "SI Units", "PKG", "Basic Units"],
        ["Human-Machine Interface", "desired volume settings", "MoEs Holder", "Detect control signal", "UC", "Use Cases of Earbuds In Use"],
        ["Climate Control Unit", "Energy", "Cooling System Design", "Cooling System", "REQ", "System Requirements"],
        ["Location", "t1", "t2", "Thing (Block)", "IBD", "Thing"],
        ["Transmission", "width", "Brake", "HSUV (Block)", "BDD", "SUV Structure"],
        ["Climate Control Unit", "iHeat", "Total Mass (Requirement)", "MoEs Holder", "PAR", "Total Mass of the VCCS"],
        ["Plumbing", "fromInLink", "Faucet", "Shower", "IBD", "Plumbing"],
    ]

    query_params_list = [
        {key: params[i] for i, key in enumerate(query_params_keys)}
        for params in params_list
    ]

    if not args.include_proprietary:
        xmi_files = xmi_files[:1]
        query_params_list = query_params_list[:1]

    # Check every input before making any API requests.
    for xmi_path in xmi_files:
        json_path = xmi_path.replace("data/xmi/", "data/json-sysml/").replace(".xml", ".json")
        for input_path in (xmi_path, json_path):
            if not Path(input_path).is_file():
                parser.error(f"Missing input: {input_path}. Follow evaluation/README.md to prepare the data.")

    # Resolve output path
    if args.output:
        output_csv = args.output
    else:
        sanitized_model_name = args.model.split('/')[-1].replace(':', '_')
        output_csv = f"evaluation/data/llm_results/llm_results_{sanitized_model_name}.csv"

    run_batch_evaluation(xmi_files, query_params_list, output_csv, args.model)
