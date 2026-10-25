"""Local, explicit inputs and strict JSON output; no implicit downloads."""
import csv
import json
from pathlib import Path

MISSING = {"", "nan", "null", "none", "na", "n/a", "<na>"}


def read_csv(path, *, delimiter=None, required_columns=()):
    path = Path(path)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        if delimiter is None:
            sample = stream.read(8192)
            stream.seek(0)
            try:
                delimiter = csv.Sniffer().sniff(sample, delimiters=";,\t").delimiter
            except csv.Error:
                delimiter = ";"
        reader = csv.DictReader(stream, delimiter=delimiter)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("CSV must have unique column names")
        missing = set(required_columns) - set(reader.fieldnames)
        if missing:
            raise ValueError(f"Missing CSV columns: {', '.join(sorted(missing))}")
        for line, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"Malformed CSV row at line {line}")
            yield line, {
                key: (None if value.strip().casefold() in MISSING else value.strip())
                for key, value in row.items()
            }


def write_json(payload, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # allow_nan=False prevents non-standard JSON NaN/Infinity from reaching the platform.
    content = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
    return path.resolve()


def read_json(path):
    def reject(value):
        raise ValueError(f"Non-finite JSON number: {value}")
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), parse_constant=reject)
