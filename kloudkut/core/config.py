"""Config loader — merges default.yaml with user config.yaml."""
import os
import re
from pathlib import Path
import yaml
from functools import lru_cache

_ENV_PATTERN = re.compile(r".*?\$\{(\w+)\}.*?")


def _load_yaml(path: str) -> dict:
    config_dir = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "..", "config"))
    real_path = os.path.realpath(path)
    # Allow paths inside config/ OR an explicit override via KLOUDKUT_CONFIG
    if not real_path.startswith(config_dir) and real_path != os.path.realpath(
        os.environ.get("KLOUDKUT_CONFIG", "")
    ):
        raise ValueError(f"Config path outside allowed directory: {path}")

    class _Loader(yaml.SafeLoader):
        pass

    def _env(loader, node):
        value = loader.construct_scalar(node)
        for g in _ENV_PATTERN.findall(value):
            value = value.replace(f"${{{g}}}", os.environ.get(g, g))
        return value

    _Loader.add_implicit_resolver("!ENV", _ENV_PATTERN, None)
    _Loader.add_constructor("!ENV", _env)

    with open(real_path, 'r') as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def load_config() -> dict:
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    default = _load_yaml(os.path.join(base_dir, "config", "default.yaml"))
    # Support --config flag via env var set by main.py
    user_path = os.environ.get("KLOUDKUT_CONFIG") or os.path.join(base_dir, "config", "config.yaml")

    if not os.path.exists(user_path):
        return default.get("resources", {})

    user = _load_yaml(user_path)
    resources = default.get("resources", {})
    for svc, vals in (user.get("resources") or {}).items():
        resources.setdefault(svc, {}).update(vals)

    # Attach notifications config so notify() can access it
    resources["notifications"] = user.get("notifications", {})

    return resources
