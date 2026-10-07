# Json-SysML

This project provides a tool to convert between XMI files (XML Metadata Interchange serialization of SysML models) and Json-SysML, a JSON-based representation of SysML models.

## Installation

1. Clone the repository and navigate to the project directory.
2. Using **Python 3.11 or later**, create a virtual environment:

```bash
python -m venv .venv
```

3. Activate the virtual environment.

On macOS or Linux:

```bash
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

On Windows Command Prompt:

```cmd
.venv\Scripts\activate.bat
```

4. Install the required dependencies:

```bash
python -m pip install -r requirements.txt
```

## Usage

The examples below use the bundled toy Small Modular Reactor (SMR) model created for testing and illustration:

- Original XMI: [`examples/xmi/toy_smr_original.xml`](examples/xmi/toy_smr_original.xml)
- Json-SysML: [`output/toy_smr.json`](output/toy_smr.json)
- Reconstructed XMI: [`output/toy_smr_reconstructed.xml`](output/toy_smr_reconstructed.xml)

Run these commands from the repository root.

### XMI to Json-SysML

To convert the toy model:

```bash
python src/catia_magic/xmi_to_jsonsysml/main.py "examples/xmi/toy_smr_original.xml" "output/toy_smr.json"
```

This command generates:

```text
output/toy_smr.json
```

The second positional argument specifies the output file. If omitted, the converter writes a `.json` file alongside the input.

Additional conversion options are available:

| Option                 | Description                                                                                                                                                                                        |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--no-clean-ids`     | Preserve the original XMI element IDs instead of remapping them to human-readable IDs.                                                                                                             |
| `--diagram-metadata` | Include diagram tagged values in the output.                                                                                                                                                       |
| `--no-minify`        | Disable minification of reused element definitions. Minification reduces the size of the output by only including the complete element definitions once and referencing them later by name and ID. |

For example:

```bash
python src/catia_magic/xmi_to_jsonsysml/main.py \
    "examples/xmi/toy_smr_original.xml" \
    "output/toy_smr.json" \
    --no-clean-ids
```

### Json-SysML to XMI

To reconstruct the toy model from its Json-SysML representation:

```bash
python src/catia_magic/jsonsysml_to_xmi/main.py "output/toy_smr.json" "output/toy_smr_reconstructed.xml"
```

This command generates:

```text
output/toy_smr_reconstructed.xml
```

The second positional argument specifies the output file. If omitted, the converter writes an `.xml` file alongside the input. The converter uses the bundled XMI template by default; `--template` selects a different template.

## Reproduction of the Evaluation Results of the Paper

To reproduce the evaluation results of the Json-SysML paper, refer to the [`evaluation/README.md`](evaluation/README.md) file for detailed instructions on preparing the evaluation data and running the evaluation scripts.

## Citation

If you use Json-SysML in your research, please cite:

```bibtex
@inproceedings{10.1145/3822455.3830325,
    author = {Khoubrane, Yousef and Elhadji Ille Gado, Nassara and Li, Rui and Danlos, Helene and Bureau, Nicolas and Benmiloud Bechet, Lies and Plana, Robert and Vazirgiannis, Michalis},
    title = {Json-SysML: A Bidirectional JSON-Based Representation for SysML Models Enabling LLM-Augmented Model-Based Systems Engineering},
    year = {2026},
    isbn = {9798400728099},
    publisher = {Association for Computing Machinery},
    address = {New York, NY, USA},
    url = {https://doi.org/10.1145/3822455.3830325},
    doi = {10.1145/3822455.3830325},
    booktitle = {Proceedings of the ACM/IEEE 29th International Conference on Model Driven Engineering Languages and Systems},
    pages = {69–79},
    numpages = {11},
    keywords = {Model-Based Systems Engineering (MBSE), Systems Modeling Language (SysML), Large Language Models, Bidirectional Model Transformation, Semantic Representation, XML Metadata Interchange (XMI), XMI Compression},
    location = {M{\'a}laga, Spain},
    series = {MODELS '26}
}
```

## License

The source code is distributed under the [BSD 3-Clause License](LICENSE). Evaluation models are obtained separately and remain subject to their upstream licenses and access restrictions.
