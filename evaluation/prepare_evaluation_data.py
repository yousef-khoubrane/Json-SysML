"""
Evaluation Data Preparation Pipeline for Json-SysML Model Conversion.

This module automates the process of preparing evaluation datasets through a
multi-stage model transformation pipeline:

    Stage 1: XMI -> JSON-SysML
        * Converts XMI models to Json-SysML format with original identifiers
        * Additionally produces cleaned (normalized) identifier variants
        * Outputs: json-sysml_original_ids/, json-sysml/

    Stage 2: JSON-SysML -> Reconstructed XMI
        * Converts both JSON-SysML variants back to XMI format
        * Enables bidirectional conversion validation
        * Outputs: reconstructed_xmi_original_ids/, reconstructed_xmi

    Stage 3: Reconstructed XMI -> Reconstructed JSON-SysML
        * Re-converts reconstructed XMI models to Json-SysML
        * Enables fidelity assessment through round-trip conversion
        * Outputs: reconstructed_json-sysml_original_ids/, reconstructed_json-sysml/

All paths are configurable, and conversion metrics are tracked and persisted.
"""

import argparse
import json
import logging
import sys
import time
import importlib.util
from pathlib import Path
from typing import Dict, List, Tuple

from tqdm import tqdm

# ============================================================================
# INITIALIZATION & MODULE LOADING
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
SRC_PATH = PROJECT_ROOT / "src" / "catia_magic"


def _load_converter_module(module_name: str, relative_path: str):
    """Load a converter module with isolated sys.path and module cache handling."""
    module_path = str(SRC_PATH / relative_path)
    spec = importlib.util.spec_from_file_location(f"{module_name}_main", module_path)
    module = importlib.util.module_from_spec(spec)

    # Add module directory to path temporarily
    converter_dir = str(SRC_PATH / relative_path.rsplit("/", 1)[0])
    sys.path.insert(0, converter_dir)

    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(converter_dir)
        # Clear local module cache to avoid downstream conflicts
        modules_to_remove = [
            key for key in sys.modules.keys()
            if any(x in key for x in [
                'diagrams', 'utils', 'act_', 'bdd_', 'pkg_', 'stm_', 'req_', 
                'uc_', 'par_', 'ibd_', 'sd_', 'common', 'helpers', 'getter_', 'variables'
            ])
        ]
        for mod in modules_to_remove:
            del sys.modules[mod]

    return module


# Load converter functions
xmi_module = _load_converter_module("xmi_to_jsonsysml", "xmi_to_jsonsysml/main.py")
xmi_to_json_sysml = xmi_module.xmi_to_json_sysml
remap_ids = xmi_module.remap_ids

json_module = _load_converter_module("jsonsysml_to_xmi", "jsonsysml_to_xmi/main.py")
json_sysml_to_xmi = json_module.json_sysml_to_xmi


# ============================================================================
# CONFIGURATION
# ============================================================================

class EvaluationConfig:
    """Configuration parameters for the evaluation pipeline."""

    # Base directories 
    XMI_INPUT_DIR = Path("evaluation/data/xmi")
    OUTPUT_BASE_DIR = Path("evaluation/data")
    RESULTS_DIR = Path("evaluation/results")

    # Model identifiers
    # Edit this list to include the names of the XMI models you wish to process.
    # Leave empty to process all .xml files in XMI_INPUT_DIR.
    MODEL_NAMES: List[str] | None = None

    # Input/Output directories
    JSON_ORIGINAL_IDS_DIR = OUTPUT_BASE_DIR / "json-sysml_original_ids"
    JSON_CLEANED_IDS_DIR = OUTPUT_BASE_DIR / "json-sysml"

    # Reconstructed XMI directories
    RECONSTRUCTED_XMI_ORIGINAL_IDS_DIR = OUTPUT_BASE_DIR / "reconstructed_xmi_original_ids"
    RECONSTRUCTED_XMI_CLEANED_IDS_DIR = OUTPUT_BASE_DIR / "reconstructed_xmi"
    
    # Reconstructed JSON directories
    RECONSTRUCTED_JSON_ORIGINAL_IDS_DIR = OUTPUT_BASE_DIR / "reconstructed_json-sysml_original_ids"
    RECONSTRUCTED_JSON_CLEANED_IDS_DIR = OUTPUT_BASE_DIR / "reconstructed_json-sysml"

    # XMI template for reconstruction
    XMI_TEMPLATE_PATH = SRC_PATH / "jsonsysml_to_xmi/resources/empty_model.xml"

    @classmethod
    def get_models_to_process(cls) -> List[str]:
        """
        Determine the list of models to process.
        Returns the explicit list if provided; otherwise, scans the input directory for all .xml files.
        """
        if cls.MODEL_NAMES:
            return cls.MODEL_NAMES
        
        if cls.XMI_INPUT_DIR.exists():
            return sorted(xml.stem for xml in cls.XMI_INPUT_DIR.glob("*.xml"))
        
        return []


# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

class TqdmLoggingHandler(logging.Handler):
    """Custom logging handler that integrates safely with tqdm progress bars."""

    def emit(self, record):
        msg = self.format(record)
        tqdm.write(msg)


def configure_logger() -> logging.Logger:
    """Initialize and configure the module logger."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    handler = TqdmLoggingHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


logger = configure_logger()


# ============================================================================
# STAGE 1: XMI TO JSON-SYSML CONVERSION
# ============================================================================

def stage1_convert_xmi_to_json(models_to_process: List[str]) -> Tuple[bool, List[Dict]]:
    """
    Convert XMI models to Json-SysML format with dual identifier handling.

    Args:
        models_to_process: List of model filenames (without extension) to convert.

    Returns:
        Tuple[bool, List[Dict]]: Success status and runtime metrics.
    """
    logger.info("=" * 80)
    logger.info("STAGE 1: XMI to JSON-SysML Conversion (Dual ID Variants)")
    logger.info("=" * 80)

    EvaluationConfig.JSON_ORIGINAL_IDS_DIR.mkdir(parents=True, exist_ok=True)
    EvaluationConfig.JSON_CLEANED_IDS_DIR.mkdir(parents=True, exist_ok=True)

    overall_success = True
    runtimes = []

    for model_name in tqdm(models_to_process, desc="Processing XMI files"):
        xmi_file = EvaluationConfig.XMI_INPUT_DIR / f"{model_name}.xml"

        if not xmi_file.exists():
            logger.warning(f"File not found: {xmi_file}. Skipping.")
            overall_success = False
            continue

        json_original_output = EvaluationConfig.JSON_ORIGINAL_IDS_DIR / f"{model_name}.json"
        json_cleaned_output = EvaluationConfig.JSON_CLEANED_IDS_DIR / f"{model_name}.json"

        logger.info(f"Converting: {model_name}")
        start_time = time.time()

        try:
            # 1a. Conversion with original IDs preserved
            model_original = xmi_to_json_sysml(str(xmi_file), clean_ids=False)
            if not model_original:
                logger.error(f"Conversion failed (original IDs): {model_name}")
                overall_success = False
                continue

            # 1b. Conversion with cleaned IDs
            model_cleaned = remap_ids(model_original)
            if not model_cleaned:
                logger.error(f"Conversion failed (cleaned IDs): {model_name}")
                overall_success = False
                continue

            # Persist both variants
            with open(json_original_output, 'w', encoding='utf-8') as f:
                json.dump(model_original, f, indent=2)

            with open(json_cleaned_output, 'w', encoding='utf-8') as f:
                json.dump(model_cleaned, f, indent=2)

            elapsed = time.time() - start_time
            runtimes.append({
                "model": model_name,
                "stage": "XMI->JSON (original)",
                "time": elapsed
            })
            logger.info(f"[OK] {model_name} ({elapsed:.2f}s) -> both variants saved")

        except Exception as e:
            logger.error(f"Error processing {model_name}: {e}")
            overall_success = False

    if not overall_success:
        logger.error("Stage 1: One or more conversions failed.")
        return False, runtimes

    logger.info("Stage 1: Completed successfully.")
    return True, runtimes


# ============================================================================
# STAGE 2: JSON-SYSML TO RECONSTRUCTED XMI CONVERSION
# ============================================================================

def stage2_convert_json_to_reconstructed_xmi(
    models_to_process: List[str], prior_runtimes: List[Dict]
) -> Tuple[bool, List[Dict]]:
    """
    Convert both JSON-SysML variants back to XMI format.

    Args:
        models_to_process: List of model filenames to convert.
        prior_runtimes: Runtime metrics from prior stages.

    Returns:
        Tuple[bool, List[Dict]]: Success status and accumulated runtime metrics.
    """
    logger.info("=" * 80)
    logger.info("STAGE 2: JSON-SysML to Reconstructed XMI (Bidirectional Validation)")
    logger.info("=" * 80)

    EvaluationConfig.RECONSTRUCTED_XMI_ORIGINAL_IDS_DIR.mkdir(parents=True, exist_ok=True)
    EvaluationConfig.RECONSTRUCTED_XMI_CLEANED_IDS_DIR.mkdir(parents=True, exist_ok=True)

    overall_success = True
    runtimes = prior_runtimes.copy()

    variants = [
        ("original", EvaluationConfig.JSON_ORIGINAL_IDS_DIR, EvaluationConfig.RECONSTRUCTED_XMI_ORIGINAL_IDS_DIR),
        ("cleaned", EvaluationConfig.JSON_CLEANED_IDS_DIR, EvaluationConfig.RECONSTRUCTED_XMI_CLEANED_IDS_DIR)
    ]

    for model_name in tqdm(models_to_process, desc="Processing JSON files"):
        for variant_type, source_dir, target_dir in variants:
            json_input = source_dir / f"{model_name}.json"
            xmi_output = target_dir / f"{model_name}.xml"

            if not json_input.exists():
                logger.warning(f"File not found: {json_input}. Skipping.")
                overall_success = False
                continue

            logger.info(f"Converting: {model_name} ({variant_type})")
            start_time = time.time()

            try:
                success = json_sysml_to_xmi(
                    json_input_path=str(json_input),
                    xmi_template_path=str(EvaluationConfig.XMI_TEMPLATE_PATH),
                    xmi_output_path=str(xmi_output)
                )

                if not success:
                    logger.error(f"Conversion failed: {model_name} ({variant_type})")
                    overall_success = False
                    continue

                elapsed = time.time() - start_time
                runtimes.append({
                    "model": f"{model_name} ({variant_type})",
                    "stage": "JSON->reconstructed XMI",
                    "time": elapsed
                })
                logger.info(f"[OK] {model_name} ({variant_type}, {elapsed:.2f}s)")

            except Exception as e:
                logger.error(f"Error processing {model_name} ({variant_type}): {e}")
                overall_success = False

    if not overall_success:
        logger.error("Stage 2: One or more conversions failed.")
        return False, runtimes

    logger.info("Stage 2: Completed successfully.")
    return True, runtimes


# ============================================================================
# STAGE 3: RECONSTRUCTED XMI TO JSON-SYSML CONVERSION
# ============================================================================

def stage3_convert_reconstructed_xmi_to_json(
    models_to_process: List[str], prior_runtimes: List[Dict]
) -> Tuple[bool, List[Dict]]:
    """
    Convert reconstructed XMI models back to Json-SysML format.

    Args:
        models_to_process: List of model filenames to convert.
        prior_runtimes: Runtime metrics from prior stages.

    Returns:
        Tuple[bool, List[Dict]]: Success status and accumulated runtime metrics.
    """
    logger.info("=" * 80)
    logger.info("STAGE 3: Reconstructed XMI to JSON-SysML (Fidelity Assessment)")
    logger.info("=" * 80)

    EvaluationConfig.RECONSTRUCTED_JSON_ORIGINAL_IDS_DIR.mkdir(parents=True, exist_ok=True)
    EvaluationConfig.RECONSTRUCTED_JSON_CLEANED_IDS_DIR.mkdir(parents=True, exist_ok=True)

    overall_success = True
    runtimes = prior_runtimes.copy()

    variants = [
        ("original", False, EvaluationConfig.RECONSTRUCTED_XMI_ORIGINAL_IDS_DIR, EvaluationConfig.RECONSTRUCTED_JSON_ORIGINAL_IDS_DIR),
        ("cleaned", True, EvaluationConfig.RECONSTRUCTED_XMI_CLEANED_IDS_DIR, EvaluationConfig.RECONSTRUCTED_JSON_CLEANED_IDS_DIR)
    ]

    for model_name in tqdm(models_to_process, desc="Processing reconstructed XMI"):
        for variant_type, use_clean_ids, input_dir, output_dir in variants:
            xmi_file = input_dir / f"{model_name}.xml"
            json_output = output_dir / f"{model_name}.json"

            if not xmi_file.exists():
                logger.warning(f"File not found: {xmi_file}. Skipping.")
                overall_success = False
                continue

            logger.info(f"Converting: {model_name} ({variant_type})")
            start_time = time.time()

            try:
                converted_model = xmi_to_json_sysml(str(xmi_file), clean_ids=use_clean_ids)
                if not converted_model:
                    logger.error(f"Conversion failed: {model_name} ({variant_type})")
                    overall_success = False
                    continue

                with open(json_output, 'w', encoding='utf-8') as f:
                    json.dump(converted_model, f, indent=2)

                elapsed = time.time() - start_time
                runtimes.append({
                    "model": f"{model_name} ({variant_type})",
                    "stage": "Reconstructed XMI->JSON",
                    "time": elapsed
                })
                logger.info(f"[OK] {model_name} ({variant_type}, {elapsed:.2f}s)")

            except Exception as e:
                logger.error(f"Error processing {model_name} ({variant_type}): {e}")
                overall_success = False

    if not overall_success:
        logger.error("Stage 3: One or more conversions failed.")
        return False, runtimes

    logger.info("Stage 3: Completed successfully.")
    return True, runtimes


# ============================================================================
# METRICS PERSISTENCE
# ============================================================================

def save_conversion_metrics(runtimes: List[Dict]) -> None:
    """Persist conversion runtime metrics to CSV format."""
    EvaluationConfig.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_file = EvaluationConfig.RESULTS_DIR / "runtimes.csv"

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("Model,Stage,Time(seconds)\n")
            for entry in runtimes:
                f.write(f"{entry['model']},{entry['stage']},{entry['time']:.4f}\n")
        logger.info(f"Runtime metrics persisted to: {output_file}")
    except Exception as e:
        logger.error(f"Failed to persist metrics: {e}")


# ============================================================================
# PIPELINE ORCHESTRATION
# ============================================================================

def main(stage: str = "all") -> bool:
    """
    Execute the evaluation data preparation pipeline.

    Args:
        stage (str): Specific stage to execute ("1", "2", "3", or "all"). Defaults to "all". Stages 2 and 3 require the outputs of previous stages.

    Returns:
        bool: True if all stages complete successfully, False otherwise.
    """
    logger.info("\n" + "=" * 80)
    logger.info("EVALUATION DATA PREPARATION PIPELINE - INITIALIZATION")
    logger.info("=" * 80 + "\n")

    try:
        # Determine target models
        models_to_process = EvaluationConfig.get_models_to_process()
        
        if not models_to_process:
            logger.error(f"No models to process. Please ensure .xml files exist in {EvaluationConfig.XMI_INPUT_DIR}")
            return False
            
        logger.info(f"Models scheduled for processing: {len(models_to_process)}")
        for m in models_to_process:
            logger.info(f"  * {m}")

        runtimes = []
        output_dirs = []

        # Stage 1: XMI -> JSON-SysML (dual variants)
        if stage in ("1", "all"):
            success, runtimes = stage1_convert_xmi_to_json(models_to_process)
            if not success:
                logger.error("Pipeline halted: Stage 1 failures detected.")
                return False
            output_dirs.extend([
                EvaluationConfig.JSON_ORIGINAL_IDS_DIR,
                EvaluationConfig.JSON_CLEANED_IDS_DIR,
            ])

        # Stage 2: JSON-SysML -> Reconstructed XMI (split directory targets)
        if stage in ("2", "all"):
            success2, runtimes = stage2_convert_json_to_reconstructed_xmi(models_to_process, runtimes)
            if not success2:
                logger.error("Pipeline halted: Stage 2 failures detected.")
                return False
            output_dirs.extend([
                EvaluationConfig.RECONSTRUCTED_XMI_ORIGINAL_IDS_DIR,
                EvaluationConfig.RECONSTRUCTED_XMI_CLEANED_IDS_DIR,
            ])

        # Stage 3: Reconstructed XMI -> JSON-SysML (dual variants)
        if stage in ("3", "all"):
            success3, runtimes = stage3_convert_reconstructed_xmi_to_json(models_to_process, runtimes)
            if not success3:
                logger.error("Pipeline halted: Stage 3 failures detected.")
                return False
            output_dirs.extend([
                EvaluationConfig.RECONSTRUCTED_JSON_ORIGINAL_IDS_DIR,
                EvaluationConfig.RECONSTRUCTED_JSON_CLEANED_IDS_DIR,
            ])

        # Persist metrics
        if runtimes:
            save_conversion_metrics(runtimes)
            output_dirs.append(EvaluationConfig.RESULTS_DIR)

        logger.info("\n" + "=" * 80)
        logger.info("[OK] PIPELINE COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)

        logger.info("\nOutput directories:")
        for directory in output_dirs:
            logger.info(f"  * {directory}")

        return True

    except Exception as e:
        logger.error(f"Unexpected error in pipeline: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Prepare evaluation datasets through the Json-SysML round-trip conversion pipeline."
    )

    parser.add_argument(
        "--input-dir",
        type=Path,
        default=EvaluationConfig.XMI_INPUT_DIR,
        help="Directory containing the input evaluation dataset (XMI files). Defaults to 'evaluation/data/xmi'."
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=EvaluationConfig.OUTPUT_BASE_DIR,
        help="Base directory where converted datasets will be written. Defaults to 'evaluation/data'."
    )

    parser.add_argument(
        "--results-dir",
        type=Path,
        default=EvaluationConfig.RESULTS_DIR,
        help="Directory where runtime metrics are saved. Defaults to 'evaluation/results'."
    )

    parser.add_argument(
        "--models",
        nargs="+",
        metavar="MODEL",
        help="Only process the specified model names (without .xml extension)."
    )

    parser.add_argument(
        "--xmi-template",
        type=Path,
        default=EvaluationConfig.XMI_TEMPLATE_PATH,
        help="XMI template used during reconstruction."
    )

    parser.add_argument(
        "--stage",
        choices=["1", "2", "3", "all"],
        default="all",
        help=(
            "Pipeline stage to execute: "
            "1=XMI->JSON, "
            "2=JSON->Reconstructed XMI (requires Stage 1 outputs), "
            "3=Reconstructed XMI->JSON (requires Stage 2 outputs), "
            "all=run the complete pipeline (default)."
        ),
    )

    args = parser.parse_args()

    # Override configuration
    EvaluationConfig.XMI_INPUT_DIR = args.input_dir
    EvaluationConfig.OUTPUT_BASE_DIR = args.output_dir
    EvaluationConfig.RESULTS_DIR = args.results_dir

    EvaluationConfig.JSON_ORIGINAL_IDS_DIR = (
        args.output_dir / "json-sysml_original_ids"
    )

    EvaluationConfig.JSON_CLEANED_IDS_DIR = (
        args.output_dir / "json-sysml"
    )

    EvaluationConfig.RECONSTRUCTED_XMI_ORIGINAL_IDS_DIR = (
        args.output_dir / "reconstructed_xmi_original_ids"
    )

    EvaluationConfig.RECONSTRUCTED_XMI_CLEANED_IDS_DIR = (
        args.output_dir / "reconstructed_xmi"
    )

    EvaluationConfig.RECONSTRUCTED_JSON_ORIGINAL_IDS_DIR = (
        args.output_dir / "reconstructed_json-sysml_original_ids"
    )

    EvaluationConfig.RECONSTRUCTED_JSON_CLEANED_IDS_DIR = (
        args.output_dir / "reconstructed_json-sysml"
    )

    EvaluationConfig.XMI_TEMPLATE_PATH = args.xmi_template
    EvaluationConfig.MODEL_NAMES = args.models

    pipeline_success = main(stage=args.stage)
    sys.exit(0 if pipeline_success else 1)
