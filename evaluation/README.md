# Evaluation

This directory contains the evaluation scripts. The repository distributes no
evaluation models, derived model files, raw LLM responses, or evaluation results.
Obtain the models locally and export them before running the scripts. Run all
commands below from the repository root after installing `requirements.txt`
with Python 3.11 or later.

## Models used in the paper

The conversion, compression, and reconstruction evaluations used the following
five models obtained from public repositories and sixteen CATIA Magic samples.
Both groups use the same local input directory: `evaluation/data/xmi/`.

### Models obtained from public repositories

| Evaluation model           | Upstream native model                                                                                                              | Local XMI filename             |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ |
| MTConnect SysML Model      | [MTConnect SysML Model.mdzip](<https://github.com/mtconnect/mtconnect_sysml_model_dev/blob/master/MTConnect%20SysML%20Model.mdzip>) | `MTConnect SysML Model.xml`  |
| openMBEE Public Server     | [openMBEE_Public_Server.mdzip](https://github.com/Open-MBEE/OpenSE-Cookbook/blob/master/Models/openMBEE_Public_Server.mdzip)        | `openMBEE_Public_Server.xml` |
| OpenSE Library             | [OpenSE Library.mdzip](<https://github.com/Open-MBEE/OpenSE-Cookbook/blob/master/Models/OpenSE%20Library.mdzip>)                    | `OpenSE Library.xml`         |
| PBR-Xref                   | [PBR-Xref.mdzip](https://github.com/Open-MBEE/OpenSE-Cookbook/blob/master/Models/PBR-Xref.mdzip)                                    | `PBR-Xref.xml`               |
| ThirtyMeterTelescope (TMT) | [TMT.mdzip](https://github.com/Open-MBEE/OpenSE-Cookbook/blob/master/Models/TMT.mdzip)                                              | `TMT.xml`                    |

Source repositories: [MTConnect](https://github.com/mtconnect/mtconnect_sysml_model_dev) and [OpenSE-Cookbook](https://github.com/Open-MBEE/OpenSE-Cookbook/tree/master/Models).

Both upstream repositories identify Apache-2.0 licensing. Their licensing does
not come from this project's BSD-3-Clause license. Follow their applicable
licenses and notices.

### CATIA Magic vendor samples

These samples require your own licensed CATIA Magic installation and applicable
rights to access and use them. Look under its `samples/SysML/` directory; exact
sample availability and filenames can differ between software versions.
Export each model using the following local XMI filename:

| Sample model                          | Local XMI filename                            |
| ------------------------------------- | --------------------------------------------- |
| basic units                           | `basic units.xml`                           |
| Excel_CSV Import SysML                | `Excel_CSV Import SysML.xml`                |
| context specific values               | `context specific values.xml`               |
| contextual relationships              | `contextual relationships.xml`              |
| WaterSupply                           | `WaterSupply.xml`                           |
| Behavior-to-Structure Synchronization | `Behavior-to-Structure Synchronization.xml` |
| Suspect Links                         | `Suspect Links.xml`                         |
| Conjugated Interface Block            | `Conjugated Interface Block.xml`            |
| SysML1.3 Interfaces Modeling          | `SysML1.3 Interfaces Modeling.xml`          |
| MultiMediaExample                     | `MultiMediaExample.xml`                     |
| TemperatureRegulationLoop             | `TemperatureRegulationLoop.xml`             |
| hybrid sport utility vehicle          | `hybrid sport utility vehicle.xml`          |
| distiller model                       | `distiller model.xml`                       |
| InvertedPendulum                      | `InvertedPendulum.xml`                      |
| climate control system                | `climate control system.xml`                |
| diagram aspects                       | `diagram aspects.xml`                       |

The LLM comprehension experiment used `PBR-Xref` and these seven vendor samples: `basic units`, `Behavior-to-Structure Synchronization`, `Conjugated Interface Block`, `context specific values`, `contextual relationships`, `Suspect Links`, and `WaterSupply`.

## Preparing the original XMI exports

1. Open a working copy of each native model in CATIA Magic/MagicDraw. For reference, we used version **2024x v6** for the exports in this evaluation.
2. When prompted for profile imports, import the default profiles. You can skip custom profiles, as we did because we did not have access to them.
3. Remove all non-SysML diagrams. Delete only the diagrams, retaining their
   constituent elements in the containment tree so shared dependencies remain
   available. Keep SysML Activity, Block Definition, Internal Block, Parametric,
   Package, Requirement, Sequence, State Machine, and Use Case diagrams.
4. Export using the application's **UML 2.5 XMI File** format option to keep the
   diagram information required by the converters. The exported files will have the `.xml` extension.
5. Create `evaluation/data/xmi/` and save each exported file using the exact filename in the tables above.

## Preparation of Evaluation Data

To prepare the evaluation data, run the following command from the project root directory:

```bash
python evaluation/prepare_evaluation_data.py
```

By default, the pipeline:

- Reads all XMI models from `evaluation/data/xmi`.
- Generates all intermediate datasets under `evaluation/data`.
- Saves runtime metrics to `evaluation/results`.
- Executes all three conversion stages:
  1. XMI → Json-SysML
  2. Json-SysML → Reconstructed XMI
  3. Reconstructed XMI → Reconstructed Json-SysML

The pipeline can also be customized through command-line arguments:

| Option                         | Description                                                                                         |
| ------------------------------ | --------------------------------------------------------------------------------------------------- |
| `--stage {1,2,3,all}`        | Execute only a specific pipeline stage. Stages 2 and 3 require the outputs of the preceding stages. |
| `--models MODEL [MODEL ...]` | Process only the specified models (without the`.xml` extension).                                  |
| `--input-dir PATH`           | Directory containing the input XMI models. Defaults to`evaluation/data/xmi`.                      |
| `--output-dir PATH`          | Base directory where the generated datasets will be written. Defaults to`evaluation/data`.        |
| `--results-dir PATH`         | Directory where runtime metrics are saved. Defaults to`evaluation/results`.                       |
| `--xmi-template PATH`        | XMI template used during reconstruction.                                                            |

For example, to process only the `PBR-Xref` and `OpenSE Library` models:

```bash
python evaluation/prepare_evaluation_data.py \
    --models "PBR-Xref" "OpenSE Library"
```

To execute only Stage 2 of the pipeline (After Stage 1 has been completed):

```bash
python evaluation/prepare_evaluation_data.py --stage 2
```

To use custom input, output, and results directories:

```bash
python evaluation/prepare_evaluation_data.py \
    --input-dir "my_evaluation/data/xmi" \
    --output-dir "my_evaluation/data" \
    --results-dir "my_evaluation/results"
```

## Compression Evaluation

The `compare_sizes.py` script evaluates the compression achieved by Json-SysML relative to the original XMI models. For each XMI/Json-SysML pair, it computes character counts, tiktoken (`cl100k_base`) token counts, and the corresponding compression ratios.

By default, it compares the models in `evaluation/data/xmi` and `evaluation/data/json-sysml`, and writes the results to `evaluation/results/compression_efficiency_results.csv`.

Run the evaluation with the default configuration:

```bash
python evaluation/compare_sizes.py
```

The script supports the following command-line arguments:

| Option              | Description                                                                            |
| ------------------- | -------------------------------------------------------------------------------------- |
| `--xmi-dir PATH`  | Directory containing the reference XMI models. Defaults to`evaluation/data/xmi`.     |
| `--json-dir PATH` | Directory containing the Json-SysML models. Defaults to`evaluation/data/json-sysml`. |
| `--output PATH`   | Output CSV file. Defaults to`evaluation/results/compression_efficiency_results.csv`. |

For example:

```bash
python evaluation/compare_sizes.py \
    --xmi-dir "my_evaluation/data/xmi" \
    --json-dir "my_evaluation/data/json-sysml" \
    --output "my_evaluation/results/compression_results.csv"
```

## Json-SysML Reconstruction Fidelity

The `compare_Json_SysMLs.py` script evaluates the semantic fidelity of the Json-SysML round-trip conversion by comparing the original Json-SysML models with their reconstructed counterparts. For each model, it computes a semantic equivalence score based on the similarity of the model elements and their properties.

By default, it compares the models in `evaluation/data/json-sysml` and `evaluation/data/reconstructed_json-sysml`, and writes the results to `evaluation/results/json_reconstruction_results.csv`.

Run the evaluation with the default configuration:

```bash
python evaluation/compare_Json_SysMLs.py
```

The script supports the following command-line arguments:

| Option                                              | Description                                                                                                        |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `--original-dir PATH`                             | Directory containing the original Json-SysML models. Defaults to`evaluation/data/json-sysml`.                    |
| `--reconstructed-dir PATH`                        | Directory containing the reconstructed Json-SysML models. Defaults to`evaluation/data/reconstructed_json-sysml`. |
| `--output PATH`                                   | Output CSV file. Defaults to`evaluation/results/json_reconstruction_results.csv`.                                |
| `--skip-diagrams DIAGRAM_TYPE [DIAGRAM_TYPE ...]` | Diagram types to exclude from the comparison. By default, all diagram types are included.                          |

For example, to exclude Sequence and State Machine Diagrams from the evaluation:

```bash
python evaluation/compare_Json_SysMLs.py \
    --skip-diagrams sd stm
```

## XMI Reconstruction Fidelity

The `compare_XMIs.py` script evaluates the fidelity of the reconstructed XMI models relative to the original XMI models. For each model, it compares the semantic elements referenced by the supported SysML diagrams and reports the percentage of faithfully reconstructed elements, along with the number of missing and mismatched elements.

By default, it compares the models in `evaluation/data/xmi` and `evaluation/data/reconstructed_xmi_original_ids`, and writes the results to `evaluation/results/xmi_reconstruction_results.csv`.

Run the evaluation with the default configuration:

```bash
python evaluation/compare_XMIs.py
```

The script supports the following command-line arguments:

| Option                                              | Description                                                                                                                                                          |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--original-dir PATH`                             | Directory containing the original XMI models. Defaults to`evaluation/data/xmi`.                                                                                    |
| `--reconstructed-dir PATH`                        | Directory containing the reconstructed XMI models. Defaults to`evaluation/data/reconstructed_xmi_original_ids`.                                                    |
| `--output PATH`                                   | Output CSV file. Defaults to`evaluation/results/xmi_reconstruction_results.csv`.                                                                                   |
| `--skip-diagrams DIAGRAM_TYPE [DIAGRAM_TYPE ...]` | Diagram types to exclude from the evaluation. Use the short Json-SysML names (e.g.,`bdd`, `ibd`, `act`). By default, all supported diagram types are included. |

For example, to exclude Activity and Parametric Diagrams from the evaluation:

```bash
python evaluation/compare_XMIs.py \
    --skip-diagrams act par
```

## LLM-Based Model Comprehension Evaluation

The `llm_prompting.py` script evaluates the comprehensibility of XMI and Json-SysML models using a large language model (LLM). For each model, it submits the original XMI and the corresponding Json-SysML representation to the same LLM along with a fixed set of model comprehension questions. The responses and token usage statistics are recorded for subsequent qualitative and quantitative analysis.

Before running the script, set the `OPENROUTER_API_KEY` environment variable with your OpenRouter API key.

Run the evaluation using the default model (`deepseek/deepseek-v4-flash`):

```bash
python evaluation/llm_prompting.py
```

You can customize the execution by specifying a different model or a custom output file path:

```bash
python evaluation/llm_prompting.py --model "openai/gpt-4o" --output "evaluation/data/llm_results/custom_metrics.csv"
```

By default, only `PBR-Xref` is evaluated. To run the seven vendor samples used
in the LLM experiment as well, pass `--include-proprietary`. This sends each
complete model payload to OpenRouter and the selected model provider; use this
option only if you have authorization to send those model contents.

Raw answers and token counts are saved in `evaluation/data/llm_results`, with a
filename derived from the selected LLM. They are ignored by Git and must not be
published. No evaluation results are distributed with this repository.
