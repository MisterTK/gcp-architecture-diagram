#!/usr/bin/env python3
"""Download and convert official GCP icons into an Iconify JSON pack.

Combines the download step (fetches the ZIP from Google) with the conversion
step (extracts SVG bodies, inlines CSS classes, writes Iconify JSON).

Usage:
    python update_icons.py                           # Download + convert → assets/gcp-icons.json
    python update_icons.py --input /path/to/icons    # Convert local icons (skip download)
    python update_icons.py --output custom.json      # Custom output path

Dependencies: Python 3 stdlib only.
"""

import argparse
import glob
import json
import os
import re
import shutil
import tempfile
import urllib.request
import zipfile

ICON_URL = "https://cloud.google.com/static/icons/files/google-cloud-icons.zip"


def download_icons(target_dir):
    """Download and extract the official GCP icon ZIP."""
    print(f"Downloading GCP icons from {ICON_URL}...")
    zip_path = os.path.join(target_dir, "gcp-icons.zip")

    try:
        urllib.request.urlretrieve(ICON_URL, zip_path)
    except Exception as e:
        print(f"ERROR: Download failed: {e}")
        print(f"\nManual download:")
        print(f"  1. Visit https://cloud.google.com/architecture/icons")
        print(f"  2. Click 'Download all icons'")
        print(f"  3. Extract and run: python update_icons.py --input /path/to/extracted")
        raise SystemExit(1)

    print("Extracting...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(target_dir)

    os.remove(zip_path)
    png_count = len(glob.glob(os.path.join(target_dir, "**/*.png"), recursive=True))
    svg_count = len(glob.glob(os.path.join(target_dir, "**/*.svg"), recursive=True))
    print(f"Extracted {png_count} PNG and {svg_count} SVG icons.")
    return target_dir


def svg_to_icon_name(filepath):
    """Convert a file path to a kebab-case icon name."""
    parts = filepath.split(os.sep)
    # The folder name is 3 levels up from the SVG file
    # e.g., .../Cloud Run/SVG/CloudRun.svg → "cloud-run"
    folder = parts[-3] if len(parts) >= 3 else os.path.splitext(parts[-1])[0]

    name = folder.lower()
    name = name.replace(" _ ", "-")   # "AI _ Machine Learning" → "ai-machine-learning"
    name = name.replace("& ", "")     # "Hybrid & Multicloud" → "hybrid-multicloud"
    name = name.replace(" ", "-")
    name = re.sub(r"[^a-z0-9-]", "", name)
    name = re.sub(r"-+", "-", name)
    name = name.strip("-")
    return name


def extract_svg_body(svg_content):
    """Extract inner SVG body, converting CSS classes to inline styles."""
    # Strip XML declaration and comments
    svg_content = re.sub(r"<\?xml[^?]*\?>\s*", "", svg_content)
    svg_content = re.sub(r"<!--.*?-->", "", svg_content, flags=re.DOTALL)

    # Extract content inside <svg> tag
    match = re.search(r"<svg[^>]*>(.*)</svg>", svg_content, re.DOTALL)
    if not match:
        return None

    body = match.group(1).strip()

    # Remove bounding_box group
    body = re.sub(
        r'<g\s+id="bounding_box">\s*<rect[^/]*/>\s*</g>', "", body, flags=re.DOTALL
    )

    # Extract CSS classes and inline them
    styles = {}
    style_match = re.search(r"<style>(.*?)</style>", body, re.DOTALL)
    if style_match:
        for rule in re.finditer(r"\.(st\d+)\s*\{([^}]+)\}", style_match.group(1)):
            styles[rule.group(1)] = rule.group(2).strip().rstrip(";")

    # Remove <defs><style>...</style></defs>
    body = re.sub(r"<defs>\s*<style>.*?</style>\s*</defs>", "", body, flags=re.DOTALL)

    # Replace class references with inline styles
    for class_name, style_val in styles.items():
        body = re.sub(rf'class="{class_name}"', f'style="{style_val}"', body)

    # Remove invisible bounding rects
    body = re.sub(r'<rect\s+style="fill:\s*none"[^/]*/>', "", body)

    # Clean up whitespace
    body = re.sub(r"\n\s*\n", "\n", body)
    return body.strip()


def convert_icons(input_dir, output_path):
    """Convert a directory of GCP SVG icons to Iconify JSON."""
    icons = {}
    entries = []

    svg_files = sorted(glob.glob(os.path.join(input_dir, "**/*.svg"), recursive=True))

    for svg_path in svg_files:
        if ".DS_Store" in svg_path:
            continue

        name = svg_to_icon_name(svg_path)
        with open(svg_path) as f:
            content = f.read()

        body = extract_svg_body(content)
        if body is None:
            print(f"  SKIP: Could not parse {svg_path}")
            continue

        icons[name] = {"body": body, "width": 512, "height": 512}
        icon_type = "category" if "Category" in svg_path else "product"
        entries.append({"name": name, "type": icon_type})

    pack = {
        "prefix": "gcp",
        "info": {
            "name": "Google Cloud Platform",
            "total": len(icons),
            "version": "2025",
            "author": {"name": "Google Cloud", "url": "https://cloud.google.com/icons"},
            "license": {
                "title": "Google Cloud Brand Guidelines",
                "url": "https://cloud.google.com/terms/branding",
            },
        },
        "lastModified": int(__import__("time").time()),
        "icons": icons,
    }

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(pack, f, indent=2)

    print(f"\nWrote {output_path} with {len(icons)} icons:")
    for e in entries:
        print(f"  gcp:{e['name']} ({e['type']})")


def main():
    parser = argparse.ArgumentParser(
        description="Download and convert GCP icons to Iconify JSON"
    )
    parser.add_argument(
        "--input", help="Path to existing extracted icons directory (skip download)"
    )
    parser.add_argument(
        "--output", default=None, help="Output JSON path (default: assets/gcp-icons.json)"
    )
    args = parser.parse_args()

    # Default output relative to this script's location
    if args.output is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        args.output = os.path.join(script_dir, "..", "assets", "gcp-icons.json")

    if args.input:
        convert_icons(args.input, args.output)
    else:
        tmpdir = tempfile.mkdtemp()
        try:
            download_icons(tmpdir)
            convert_icons(tmpdir, args.output)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    print("\nDone.")


if __name__ == "__main__":
    main()
