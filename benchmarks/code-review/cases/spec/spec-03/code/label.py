import csv
import re

MAX_LABEL_LEN = 40
STUDY_CODE_PATTERN = r"[A-Z0-9]{3,8}"


def make_label(sample_id, study_code, collected_at):
    """Build a sample label in the form STUDY-NNNNNN-YYYYMMDD."""
    if sample_id < 0 or sample_id > 999999:
        raise ValueError("sample_id out of range")
    if not re.fullmatch(STUDY_CODE_PATTERN, study_code):
        raise ValueError("invalid study_code")
    label = f"{study_code}-{sample_id:06d}-{collected_at:%Y%m%d}"
    if len(label) > MAX_LABEL_LEN:
        raise ValueError("label too long")
    return label


def make_label_batch(study_code, start_id, count, collected_at):
    """Generate consecutive labels starting at start_id."""
    if count < 1:
        raise ValueError("count must be at least 1")
    labels = []
    for offset in range(count):
        labels.append(make_label(start_id + offset, study_code, collected_at))
    return labels


def register_labels(labels, path):
    """Append labels to the sample register CSV."""
    with open(path, "a", newline="") as handle:
        writer = csv.writer(handle)
        for text in labels:
            writer.writerow([text])


def run_batch(study_code, start_id, count, collected_at, register_path):
    """Generate a batch and return the labels."""
    labels = make_label_batch(study_code, start_id, count, collected_at)
    return labels
