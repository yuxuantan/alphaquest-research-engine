from __future__ import annotations

from propstack.data.clean import clean_data
from propstack.data.features import build_features
from propstack.data.quality import save_pipeline_outputs


def prepare_data(data_config: dict, output_dir=None):
    cleaned, quality_report, missing = clean_data(data_config)
    features = build_features(cleaned, data_config)
    if output_dir:
        save_pipeline_outputs(cleaned, features, quality_report, missing, output_dir)
    return features, quality_report
