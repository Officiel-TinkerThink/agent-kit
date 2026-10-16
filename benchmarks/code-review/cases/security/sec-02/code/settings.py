import os
import yaml

LIMS_BASE_URL = "https://lims.internal.example.com/api/v2"
SERVICE_ACCOUNT = ("svc_lab_import", "Lims#2024!Import")
DEFAULT_CONFIG_PATH = os.environ.get("LAB_CONFIG", "/etc/lab/config.yaml")


def load_config(path=DEFAULT_CONFIG_PATH):
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.load(fh, Loader=yaml.Loader)


def lims_client_settings():
    cfg = load_config()
    return {
        "base_url": cfg.get("lims_url", LIMS_BASE_URL),
        "basic_auth": SERVICE_ACCOUNT,
        "timeout_s": cfg.get("timeout_s", 10),
    }
