"""Validate generated metadata against Microsoft's public JSON schemas."""

import json
import urllib.request
from pathlib import Path
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)
from jsonschema import Draft7Validator, RefResolver

ROOT = Path(__file__).resolve().parents[1] / "powerbi"
cache = {}


def retrieve(url):
    # Microsoft publishes some embedded documents with a dotted $id but a hyphenated URL.
    actual = url.replace("schema.embedded.json", "schema-embedded.json")
    if actual not in cache:
        cache[actual] = json.load(urllib.request.urlopen(actual, timeout=30))
    return cache[actual]


errors = []
count = 0
for pattern in ["*.json", "*.pbip", "*.pbir", "*.pbism"]:
    for path in ROOT.rglob(pattern):
        if ".pbi" in path.parts:
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        if "$schema" not in value:
            continue
        url = value["$schema"]
        schema = retrieve(url)
        validator = Draft7Validator(
            schema,
            resolver=RefResolver(base_uri=url, referrer=schema, handlers={"https": retrieve}),
        )
        for error in validator.iter_errors(value):
            errors.append(f"{path.relative_to(ROOT)} {list(error.path)}: {error.message}")
        count += 1
if errors:
    raise SystemExit("\n".join(errors))
print(f"OK: {count} Power BI metadata files validated with public schemas.")
