#!/usr/bin/env python3
"""Publish only complete builds, with package and kernel feature checks."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

from verify_config import read_config

RECIPE = Path(__file__).resolve().parents[1]
REQUIRED_PACKAGES = {
    "luci-app-openclash", "luci-app-passwall", "xray-core", "sing-box",
    "luci-app-ddns", "ddns-scripts-cloudflare", "ddns-scripts-dnspod-v3",
    "luci-app-bandix", "bandix", "luci-app-appfilter", "appfilter", "kmod-oaf",
    "luci-app-nlbwmon", "luci-app-vnstat2", "luci-theme-argon",
    "qemu-ga", "miniupnpd-nftables", "luci-app-wol",
}
FORBIDDEN_PACKAGES = {
    "luci-app-passwall2", "luci-app-ddns-go", "ddns-go", "luci-app-vlmcsd",
    "vlmcsd", "luci-app-sqm", "sqm-scripts", "luci-app-eqos", "luci-app-wrtbwmon",
}
KERNEL_FEATURES = {
    "CONFIG_BPF", "CONFIG_BPF_SYSCALL", "CONFIG_BPF_JIT",
    "CONFIG_DEBUG_INFO_BTF", "CONFIG_NET_CLS_BPF", "CONFIG_NET_ACT_BPF",
    "CONFIG_VIRTIO_NET", "CONFIG_VIRTIO_BLK", "CONFIG_SCSI_VIRTIO",
    "CONFIG_VIRTIO_BALLOON", "CONFIG_VIRTIO_CONSOLE",
}


def validate(work):
    target = work / "bin/targets/x86/64"
    manifests = list(target.glob("*.manifest"))
    if not manifests:
        raise RuntimeError("No firmware package manifest")
    for manifest in manifests:
        packages = {line.split()[0] for line in manifest.read_text().splitlines() if line.strip()}
        missing = REQUIRED_PACKAGES - packages
        unwanted = FORBIDDEN_PACKAGES & packages
        if missing or unwanted:
            raise RuntimeError(f"{manifest.name}: missing={sorted(missing)}, unwanted={sorted(unwanted)}")
    kernels = list((work / "build_dir").glob("target-*/linux-x86_64/linux-*/.config"))
    if len(kernels) != 1:
        raise RuntimeError(f"Expected one built kernel configuration, got {len(kernels)}")
    kernel = read_config(kernels[0])
    missing = {key for key in KERNEL_FEATURES if kernel.get(key) not in {"y", "m"}}
    if missing:
        raise RuntimeError(f"Missing Bandix/PVE kernel features: {sorted(missing)}")
    # All four boot/filesystem combinations must exist.
    for fs in ("ext4", "squashfs"):
        for suffix in ("combined.img.gz", "combined-efi.img.gz"):
            if not list(target.glob(f"*-{fs}-{suffix}")):
                raise RuntimeError(f"Missing {fs}/{suffix}")
    if not list(target.glob("*.qcow2*")):
        raise RuntimeError("Missing PVE QCOW2 images")
    return target, kernels[0]


def main():
    work, output = (Path(arg).resolve() for arg in sys.argv[1:3])
    target, kernel_config = validate(work)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise RuntimeError("Output directory must be empty")
    for path in target.iterdir():
        if path.is_file() and (
            path.name.endswith((".img.gz", ".qcow2", ".qcow2.gz", ".manifest", ".buildinfo"))
            or path.name == "profiles.json"
        ):
            shutil.copy2(path, output / path.name)
    shutil.copyfile(work / ".config", output / "resolved.config")
    shutil.copyfile(kernel_config, output / "kernel.config")
    shutil.copyfile(work / "build-lock.json", output / "build-lock.json")
    shutil.copyfile(RECIPE / "README.md", output / "README.zh-CN.md")
    lock = json.loads((work / "build-lock.json").read_text())
    report = (
        f"# ImmortalWrt {lock['release']} PVE\n\n"
        f"- Recipe commit: {os.getenv('GITHUB_SHA', 'local')}\n"
        f"- Official release source: {lock['core']['commit']}\n"
        f"- Build: {os.getenv('GITHUB_RUN_NUMBER', 'local')}/{os.getenv('GITHUB_RUN_ATTEMPT', '1')}\n"
        f"- Mihomo: {lock['mihomo']['version']} (baseline amd64, SHA256 checked)\n"
        f"- Bandix UI: {lock['bandix_luci']['release']}; backend uses upstream checksummed binary.\n"
        "- Official feeds: 25.12 maintenance revisions recorded in build-lock.json.\n"
        "- Package inclusion and Bandix/PVE kernel checks: passed.\n\n"
        "Packages: OpenClash, PassWall (Xray + sing-box), native DDNS, Bandix,\n"
        "OpenAppFilter, nlbwmon, vnStat2, Argon, WOL, UPnP and qemu-ga.\n\n"
        "No KMS, DDNS-Go, PassWall2, SQM, old wrtbwmon or EQoS.\n\n"
        "This is a custom build from an official release, not an official binary.\n"
        "Runtime compatibility and traffic accounting are NOT established by build success.\n"
        "Use an isolated PVE test VM first. Read README.zh-CN.md before installation.\n"
        "Do not restore a complete 18.06 configuration archive.\n"
    )
    (output / "BUILD-INFO.md").write_text(report, encoding="utf-8")
    checksums = [
        f"{sha256_file(path)}  {path.name}"
        for path in sorted(output.iterdir()) if path.is_file()
    ]
    (output / "SHA256SUMS").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    print(f"Collected {len(checksums)} files with validated manifests and kernel features")


def sha256_file(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


if __name__ == "__main__":
    main()
