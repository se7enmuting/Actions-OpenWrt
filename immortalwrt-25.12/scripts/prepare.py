#!/usr/bin/env python3
"""Fetch the reviewed sources without running the legacy 18.06 DIY scripts."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

RECIPE = Path(__file__).resolve().parents[1]


def checkout(spec, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        raise RuntimeError(f"Refusing to overwrite a nonempty source directory: {destination}")
    subprocess.run(["git", "init", str(destination)], check=True)
    subprocess.run(["git", "-C", str(destination), "remote", "add", "origin", spec["url"]], check=True)
    subprocess.run(["git", "-C", str(destination), "fetch", "--depth=1", "origin", spec["commit"]], check=True)
    subprocess.run(["git", "-C", str(destination), "checkout", "--detach", "FETCH_HEAD"], check=True)
    actual = subprocess.check_output(["git", "-C", str(destination), "rev-parse", "HEAD"], text=True).strip()
    if actual != spec["commit"]:
        raise RuntimeError(f"Source revision mismatch: {destination}")


def main():
    work = Path(sys.argv[1]).resolve()
    lock = json.loads((RECIPE / "sources.lock.json").read_text(encoding="utf-8"))
    checkout(lock["core"], work)
    lines = [
        f"src-git {name} {spec['url']}^{spec['commit']}"
        for name, spec in lock["feeds"].items()
    ]
    (work / "feeds.conf.default").write_text("\n".join(lines) + "\n", encoding="utf-8")
    checkout(lock["bandix_backend"], work / "package/custom/bandix-backend")
    checkout(lock["bandix_luci"], work / "package/custom/bandix-luci")
    shutil.copyfile(RECIPE / "config.seed", work / ".config")
    shutil.copytree(RECIPE / "files", work / "files", dirs_exist_ok=True)
    for f in (work / "files/etc/uci-defaults").iterdir():
        f.chmod(0o755)

    # Retain the upstream verified binary recipe for Bandix. Its Makefile pins
    # the architecture-specific binary hash; it is NOT compiled from Rust here.
    mihomo = lock["mihomo"]
    archive = work / "mihomo.gz"
    with urllib.request.urlopen(mihomo["url"], timeout=120) as response, archive.open("wb") as out:
        shutil.copyfileobj(response, out)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != mihomo["sha256"]:
        raise RuntimeError("Mihomo SHA256 mismatch")
    core = work / "files/etc/openclash/core/clash_meta"
    core.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(archive, "rb") as source, core.open("wb") as target:
        shutil.copyfileobj(source, target)
    core.chmod(0o755)
    archive.unlink()
    # OpenClash writes the architecture choice to UCI; compatible amd64 avoids
    # assuming AVX support in either PVE guest.
    (work / "build-lock.json").write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared ImmortalWrt {lock['release']} at {lock['core']['commit']}")


if __name__ == "__main__":
    main()
