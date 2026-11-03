#!/usr/bin/env python3
"""Fail if defconfig silently drops any selected feature or adds an exclusion."""
from pathlib import Path
import re
import sys


def read_config(path):
    result = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"(CONFIG_[\w-]+)=(.*)", line)
        disabled = re.fullmatch(r"# (CONFIG_[\w-]+) is not set", line)
        if match:
            if match[1] in result:
                raise ValueError(f"Duplicate configuration key: {match[1]}")
            result[match[1]] = match[2]
        elif disabled:
            if disabled[1] in result:
                raise ValueError(f"Duplicate configuration key: {disabled[1]}")
            result[disabled[1]] = "n"
    return result


def verify(seed, actual):
    return [
        f"{key}: requested {value}, resolved {actual.get(key, 'n')}"
        for key, value in seed.items() if actual.get(key, "n") != value
    ]


if __name__ == "__main__":
    expected = read_config(sys.argv[1])
    errors = verify(expected, read_config(sys.argv[2]))
    if errors:
        raise SystemExit("Configuration mismatch:\n" + "\n".join(errors))
    print(f"All {len(expected)} explicit build settings verified.")
