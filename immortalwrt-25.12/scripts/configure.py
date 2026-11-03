#!/usr/bin/env python3
"""Install requested LuCI packages, then load the seed AFTER feeds refreshes."""
from pathlib import Path
import shutil
import subprocess
import sys

from verify_config import read_config

recipe = Path(__file__).resolve().parents[1]
work = Path(sys.argv[1]).resolve()
settings = read_config(recipe / "config.seed")
packages = [
    key.removeprefix("CONFIG_PACKAGE_")
    for key, value in settings.items()
    if key.startswith("CONFIG_PACKAGE_") and value == "y" and "_INCLUDE_" not in key
]
# packages feed is installed first for the target's default core dependencies.
# Only requested LuCI apps and their dependencies are linked, keeping unrelated
# application Kconfig errors out of this firmware's dependency graph.
subprocess.run(["./scripts/feeds", "install", *packages], cwd=work, check=True)
shutil.copyfile(recipe / "config.seed", work / ".config")
print("Loaded requested configuration after feed installation")
