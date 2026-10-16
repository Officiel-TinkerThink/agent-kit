import yaml

DEFAULT_THRESHOLDS = {"ph_max": 8.5, "ph_min": 6.5}


def load_thresholds(path):
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    merged = dict(DEFAULT_THRESHOLDS)
    merged.update({k: float(v) for k, v in data.get("thresholds", {}).items()})
    return merged


def thresholds_summary(thresholds):
    return ", ".join(f"{k}={v}" for k, v in sorted(thresholds.items()))
