#!/usr/bin/env python3
"""GCP Architecture Diagram Renderer.

Reads a JSON diagram specification and the GCP Iconify icon pack,
produces a pixel-perfect SVG with inline vector icons.

Usage:
    python render.py --spec diagram.json --icons gcp-icons.json -o output.svg
    python render.py --spec diagram.json --icons gcp-icons.json -o output.html
    python render.py --spec diagram.json --icons gcp-icons.json --validate-only
    python render.py --spec - --icons gcp-icons.json -o output.svg   # stdin

Dependencies: Python 3 stdlib only (json, argparse, sys, os, html).
"""

import json
import argparse
import sys
import os
from html import escape as html_escape

# ── Layout Constants ─────────────────────────────────────────────────────────

W = 1200
MARGIN = 24
ICON_S = 36
ROW_PAD = 14
ROW_H = 95
ROW_H_DOUBLE = 165
ARROW_GAP = 28
SECTION_GAP = 8
CONTAINER_LABEL_H = 32
CONTAINER_PAD_BOTTOM = 10
TITLE_H = 50
TITLE_GAP = 10
LEGEND_H = 30
BRIDGE_H = 60
SPLIT_GAP_RATIO = 0.03
FONT = "'Google Sans','Helvetica Neue',Helvetica,Arial,sans-serif"

# ── GCP Brand Colors ─────────────────────────────────────────────────────────

COLORS = {
    "blue":   {"border": "#4285F4", "bg": "#E8F0FE", "label": "#1967D2"},
    "green":  {"border": "#34A853", "bg": "#E6F4EA", "label": "#1B5E20"},
    "red":    {"border": "#EA4335", "bg": "#FCE8E6", "label": "#C62828"},
    "yellow": {"border": "#F9A825", "bg": "#FFF8E1", "label": "#E65100"},
    "purple": {"border": "#7B1FA2", "bg": "#F3E8FD", "label": "#4A148C"},
    "gray":   {"border": "#9AA0A6", "bg": "#F8F9FA", "label": "#5F6368"},
    "navy":   {"border": "#1A237E", "bg": "#E8EAF6", "label": "#1A237E"},
    "orange": {"border": "#FB8C00", "bg": "#FFF3E0", "label": "#E65100"},
}

VALID_TYPES = {"layer", "arrow", "container", "split", "bridge", "legend"}


# ── Icon Pack ────────────────────────────────────────────────────────────────

class IconPack:
    """Load and serve SVG icon bodies from an Iconify JSON pack."""

    def __init__(self, json_path):
        with open(json_path) as f:
            data = json.load(f)
        self.icons = data.get("icons", {})

    def get(self, icon_id):
        """Return (body, width, height) or None."""
        if ":" in icon_id:
            icon_id = icon_id.split(":", 1)[1]
        icon = self.icons.get(icon_id)
        if not icon:
            return None
        return icon["body"], icon.get("width", 512), icon.get("height", 512)

    def has(self, icon_id):
        if ":" in icon_id:
            icon_id = icon_id.split(":", 1)[1]
        return icon_id in self.icons

    def list_ids(self):
        return sorted(self.icons.keys())


# ── Validator ────────────────────────────────────────────────────────────────

def validate_spec(spec, icons):
    """Validate a diagram spec. Returns (errors, warnings)."""
    errors = []
    warnings = []

    if "title" not in spec:
        warnings.append("No 'title' field in spec")

    elements = spec.get("elements")
    if not elements or not isinstance(elements, list):
        errors.append("Missing or empty 'elements' array in spec")
        return errors, warnings

    title_color = spec.get("titleColor", "blue")
    if title_color not in COLORS:
        errors.append(f"Unknown titleColor '{title_color}'. Valid: {', '.join(sorted(COLORS))}")

    def check(elems, path="elements"):
        for i, elem in enumerate(elems):
            ep = f"{path}[{i}]"
            etype = elem.get("type")

            if etype not in VALID_TYPES:
                errors.append(f"{ep}: Unknown type '{etype}'. Valid: {', '.join(sorted(VALID_TYPES))}")
                continue

            color = elem.get("color", "gray")
            if etype != "legend" and color not in COLORS:
                errors.append(f"{ep}: Unknown color '{color}'. Valid: {', '.join(sorted(COLORS))}")

            if etype == "layer":
                services = elem.get("services")
                if not services or not isinstance(services, list):
                    errors.append(f"{ep}: Layer must have a non-empty 'services' array")
                    continue
                if len(services) > 10:
                    warnings.append(f"{ep}: {len(services)} services in one layer — consider splitting")
                for j, svc in enumerate(services):
                    icon_id = svc.get("icon", "")
                    if icon_id and not icons.has(icon_id):
                        errors.append(
                            f"{ep}.services[{j}]: Icon '{icon_id}' not found in pack. "
                            f"Available: {', '.join(icons.list_ids()[:10])}..."
                        )
                    if not svc.get("label"):
                        warnings.append(f"{ep}.services[{j}]: Missing 'label'")

            elif etype == "container":
                children = elem.get("elements")
                if not children or not isinstance(children, list):
                    errors.append(f"{ep}: Container must have a non-empty 'elements' array")
                else:
                    check(children, f"{ep}.elements")

            elif etype == "split":
                children = elem.get("elements")
                if not children or not isinstance(children, list) or len(children) < 2:
                    errors.append(f"{ep}: Split must have at least 2 elements")
                else:
                    ratios = elem.get("ratios", [1] * len(children))
                    if len(ratios) != len(children):
                        errors.append(f"{ep}: 'ratios' length ({len(ratios)}) != elements count ({len(children)})")
                    if any(r <= 0 for r in ratios):
                        errors.append(f"{ep}: All ratios must be > 0")
                    for k, sub in enumerate(children):
                        check([sub], f"{ep}.elements")

            elif etype == "legend":
                items = elem.get("items")
                if not items or not isinstance(items, list):
                    warnings.append(f"{ep}: Legend has no items")
                else:
                    for j, item in enumerate(items):
                        c = item.get("color", "")
                        if c and c not in COLORS:
                            errors.append(f"{ep}.items[{j}]: Unknown color '{c}'")

    check(elements)
    return errors, warnings


# ── Height Calculator ────────────────────────────────────────────────────────

def calc_height(elements):
    """Calculate total pixel height for a list of elements."""
    h = 0
    for elem in elements:
        h += _elem_height(elem)
    return h


def _elem_height(elem):
    etype = elem.get("type")
    if etype == "layer":
        n = len(elem.get("services", []))
        return (ROW_H_DOUBLE if n > 6 else ROW_H) + SECTION_GAP
    elif etype == "arrow":
        return ARROW_GAP
    elif etype == "bridge":
        return BRIDGE_H
    elif etype == "legend":
        return LEGEND_H
    elif etype == "container":
        inner = calc_height(elem.get("elements", []))
        return CONTAINER_LABEL_H + inner + CONTAINER_PAD_BOTTOM + SECTION_GAP
    elif etype == "split":
        max_h = 0
        for sub in elem.get("elements", []):
            max_h = max(max_h, _elem_height(sub))
        return max_h + SECTION_GAP
    return 0


# ── SVG Renderer ─────────────────────────────────────────────────────────────

class SvgRenderer:
    """Renders a validated spec into SVG."""

    def __init__(self, spec, icons):
        self.spec = spec
        self.icons = icons
        self.parts = []
        self.width = spec.get("width", W)

    # ── SVG Primitives ───────────────────────────────────────────────────

    def _rect(self, x, y, w, h, fill="none", stroke="#DADCE0", sw=1.5, rx=10):
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
            f'rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
        )

    def _text(self, x, y, label, size=10, color="#202124", weight="600", anchor="middle"):
        for i, line in enumerate(str(label).split("\n")):
            safe = html_escape(line)
            self.parts.append(
                f'<text x="{x}" y="{y + i * (size + 3)}" font-family="{FONT}" '
                f'font-size="{size}" fill="{color}" font-weight="{weight}" '
                f'text-anchor="{anchor}">{safe}</text>'
            )

    def _icon_svg(self, icon_id, x, y, size=ICON_S):
        data = self.icons.get(icon_id)
        if data:
            body, vw, vh = data
            self.parts.append(
                f'<svg x="{x}" y="{y}" width="{size}" height="{size}" '
                f'viewBox="0 0 {vw} {vh}">{body}</svg>'
            )
        else:
            # Placeholder square
            self._rect(x, y, size, size, fill="#F0F0F0", stroke="#DADCE0", sw=1, rx=4)
            self._text(x + size // 2, y + size // 2 + 4, "?", size=12, color="#999")

    def _icon_box(self, cx, y, icon_id, label, sublabel=""):
        self._icon_svg(icon_id, cx - ICON_S // 2, y)
        self._text(cx, y + ICON_S + 13, label, size=10, weight="700")
        if sublabel:
            self._text(cx, y + ICON_S + 25, sublabel, size=8, weight="400", color="#757575")

    def _row_of_icons(self, services, y, x_start, x_end):
        n = len(services)
        if n == 0:
            return
        spacing = (x_end - x_start) / (n + 1)
        for i, svc in enumerate(services):
            cx = x_start + spacing * (i + 1)
            self._icon_box(cx, y, svc.get("icon", ""), svc.get("label", ""), svc.get("sublabel", ""))

    def _section_label(self, x, y, label, color="#1967D2"):
        self._text(x, y, label, size=10, color=color, weight="800", anchor="start")

    def _arrow_down(self, cx, y, color="#9AA0A6", length=18):
        self.parts.append(
            f'<path d="M{cx},{y} L{cx},{y + length}" '
            f'stroke="{color}" stroke-width="2" fill="none"/>'
        )
        self.parts.append(
            f'<polygon points="{cx},{y + length} {cx - 5},{y + length - 7} '
            f'{cx + 5},{y + length - 7}" fill="{color}"/>'
        )

    def _arrow_bidir(self, cx, y, color="#EA4335", length=24):
        self.parts.append(
            f'<path d="M{cx},{y} L{cx},{y + length}" '
            f'stroke="{color}" stroke-width="2.5" fill="none"/>'
        )
        # Down arrowhead
        self.parts.append(
            f'<polygon points="{cx},{y + length} {cx - 5},{y + length - 7} '
            f'{cx + 5},{y + length - 7}" fill="{color}"/>'
        )
        # Up arrowhead
        self.parts.append(
            f'<polygon points="{cx},{y} {cx - 5},{y + 7} '
            f'{cx + 5},{y + 7}" fill="{color}"/>'
        )

    # ── Element Renderers ────────────────────────────────────────────────

    def _render_layer(self, elem, y, x_start, x_end):
        services = elem.get("services", [])
        label = elem.get("label", "")
        colors = COLORS.get(elem.get("color", "gray"), COLORS["gray"])
        n = len(services)
        rh = ROW_H_DOUBLE if n > 6 else ROW_H

        self._rect(x_start, y, x_end - x_start, rh,
                   fill=colors["bg"], stroke=colors["border"], sw=2, rx=8)

        if label:
            self._section_label(x_start + ROW_PAD, y + 18, label, colors["label"])

        icon_y = y + (28 if label else 16)
        if n <= 6:
            self._row_of_icons(services, icon_y, x_start, x_end)
        else:
            mid = (n + 1) // 2
            self._row_of_icons(services[:mid], icon_y, x_start, x_end)
            self._row_of_icons(services[mid:], icon_y + 70, x_start + 60, x_end - 60)

        return y + rh + SECTION_GAP

    def _render_arrow(self, elem, y, x_start, x_end, prev_elem=None):
        colors = COLORS.get(elem.get("color", "gray"), COLORS["gray"])

        # When arrow follows a split, render one arrow per column center
        if prev_elem and prev_elem.get("type") == "split":
            children = prev_elem.get("elements", [])
            ratios = prev_elem.get("ratios", [1] * len(children))
            total_ratio = sum(ratios)
            available_w = x_end - x_start
            gap = available_w * SPLIT_GAP_RATIO
            usable_w = available_w - gap * (len(children) - 1)
            cx = x_start
            for i in range(len(children)):
                col_w = usable_w * ratios[i] / total_ratio
                col_cx = cx + col_w / 2
                self._arrow_down(col_cx, y + 4, colors["border"])
                cx += col_w + gap
        else:
            cx = (x_start + x_end) // 2
            self._arrow_down(cx, y + 4, colors["border"])

        label = elem.get("label", "")
        if label:
            self._text((x_start + x_end) // 2, y + ARROW_GAP - 2, label,
                       size=8, color="#757575", weight="400")
        return y + ARROW_GAP

    def _render_bridge(self, elem, y, x_start, x_end):
        colors = COLORS.get(elem.get("color", "red"), COLORS["red"])
        cx = (x_start + x_end) // 2
        self._arrow_bidir(cx, y + 4, colors["border"])
        label = elem.get("label", "")
        if label:
            self._text(cx, y + 42, label, size=10, color=colors["label"], weight="700")
        sublabel = elem.get("sublabel", elem.get("description", ""))
        if sublabel:
            self._text(cx, y + 54, sublabel, size=8, color="#757575", weight="400")
        return y + BRIDGE_H

    def _render_container(self, elem, y, x_start, x_end):
        children = elem.get("elements", [])
        label = elem.get("label", "")
        colors = COLORS.get(elem.get("color", "gray"), COLORS["gray"])
        inner_h = calc_height(children)
        total_h = CONTAINER_LABEL_H + inner_h + CONTAINER_PAD_BOTTOM

        # Outer box
        self._rect(x_start - 4, y, (x_end - x_start) + 8, total_h,
                   fill=colors["bg"], stroke=colors["border"], sw=3, rx=12)

        if label:
            self._section_label(x_start + 8, y + 22, label, colors["label"])

        # Render children (pass prev_elem for arrow-after-split awareness)
        inner_y = y + CONTAINER_LABEL_H
        prev_child = None
        for child in children:
            inner_y = self._render_element(child, inner_y, x_start + 4, x_end - 4, prev_child)
            prev_child = child

        return y + total_h + SECTION_GAP

    def _render_split(self, elem, y, x_start, x_end):
        children = elem.get("elements", [])
        ratios = elem.get("ratios", [1] * len(children))
        total_ratio = sum(ratios)
        available_w = x_end - x_start
        gap = available_w * SPLIT_GAP_RATIO
        usable_w = available_w - gap * (len(children) - 1)

        # Max height across columns
        max_h = 0
        for sub in children:
            max_h = max(max_h, _elem_height(sub))

        cx = x_start
        for i, sub in enumerate(children):
            col_w = usable_w * ratios[i] / total_ratio
            self._render_element(sub, y, cx, cx + col_w)
            cx += col_w + gap

        return y + max_h + SECTION_GAP

    def _render_legend(self, elem, y, x_start, x_end):
        items = elem.get("items", [])
        lx = x_start
        for item in items:
            c = COLORS.get(item.get("color", "gray"), COLORS["gray"])
            self._rect(lx, y + 6, 14, 10, fill=c["bg"], stroke=c["border"], sw=1, rx=2)
            self._text(lx + 22, y + 15, item.get("label", ""), size=8,
                       weight="400", color="#5F6368", anchor="start")
            lx += 140
        return y + LEGEND_H

    def _render_element(self, elem, y, x_start, x_end, prev_elem=None):
        etype = elem.get("type")
        if etype == "layer":
            return self._render_layer(elem, y, x_start, x_end)
        elif etype == "arrow":
            return self._render_arrow(elem, y, x_start, x_end, prev_elem)
        elif etype == "bridge":
            return self._render_bridge(elem, y, x_start, x_end)
        elif etype == "container":
            return self._render_container(elem, y, x_start, x_end)
        elif etype == "split":
            return self._render_split(elem, y, x_start, x_end)
        elif etype == "legend":
            return self._render_legend(elem, y, x_start, x_end)
        return y

    # ── Top-level Render ─────────────────────────────────────────────────

    def render(self):
        """Produce complete SVG string."""
        title = self.spec.get("title", "")
        subtitle = self.spec.get("subtitle", "")
        title_color = COLORS.get(self.spec.get("titleColor", "blue"), COLORS["blue"])
        elements = self.spec.get("elements", [])

        y = 0

        # Title bar
        if title:
            self._rect(0, y, self.width, TITLE_H,
                       fill=title_color["border"], stroke="none", sw=0, rx=0)
            self._text(self.width // 2, y + 32, title, size=18, color="white", weight="700")
            y += TITLE_H + TITLE_GAP

        # Subtitle
        if subtitle:
            self._text(self.width // 2, y + 12, subtitle, size=11, color="#5F6368", weight="400")
            y += 22

        # Content (pass prev_elem for arrow-after-split awareness)
        prev_elem = None
        for elem in elements:
            y = self._render_element(elem, y, MARGIN, self.width - MARGIN, prev_elem)
            prev_elem = elem

        total_h = y + 16  # bottom padding

        return (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {self.width} {total_h}" '
            f'width="{self.width}" height="{total_h}">\n'
            f'<style>text {{ font-family: {FONT}; }}</style>\n'
            f'<rect width="{self.width}" height="{total_h}" fill="white"/>\n'
            f'{"".join(self.parts)}\n'
            f'</svg>'
        )

    def render_html(self):
        """Produce SVG wrapped in an HTML viewer."""
        svg = self.render()
        title = html_escape(self.spec.get("title", "GCP Architecture"))
        return (
            f'<!DOCTYPE html>\n'
            f'<html lang="en">\n<head>\n'
            f'<meta charset="UTF-8">\n'
            f'<meta name="viewport" content="width=device-width,initial-scale=1.0">\n'
            f'<title>{title}</title>\n'
            f'<style>\n'
            f"body {{ font-family: {FONT}; background: #f8f9fa; "
            f"margin: 0; padding: 40px; display: flex; justify-content: center; }}\n"
            f".wrap {{ background: white; border-radius: 12px; padding: 24px; "
            f"box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08); "
            f"display: inline-block; max-width: 100%; overflow-x: auto; }}\n"
            f'</style>\n</head>\n<body>\n'
            f'<div class="wrap">\n{svg}\n</div>\n'
            f'</body>\n</html>'
        )


# ── Public API ───────────────────────────────────────────────────────────────

def render(spec, icons_path, html=False):
    """Validate and render a diagram spec. Returns SVG or HTML string.

    Raises SystemExit on validation errors.
    """
    icons = IconPack(icons_path)
    errors, warnings = validate_spec(spec, icons)

    for w in warnings:
        print(f"  WARN: {w}", file=sys.stderr)
    if errors:
        print(f"\n{len(errors)} validation error(s):", file=sys.stderr)
        for e in errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    renderer = SvgRenderer(spec, icons)
    return renderer.render_html() if html else renderer.render()


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Render a GCP architecture diagram from a JSON spec.")
    parser.add_argument("--spec", required=True,
                        help="JSON spec file (use '-' for stdin)")
    parser.add_argument("--icons", required=True,
                        help="Path to gcp-icons.json")
    parser.add_argument("-o", "--output", default="diagram.svg",
                        help="Output file path (default: diagram.svg)")
    parser.add_argument("--html", action="store_true",
                        help="Force HTML output (auto-detected from .html extension)")
    parser.add_argument("--validate-only", action="store_true",
                        help="Validate the spec without rendering")
    args = parser.parse_args()

    # Load spec
    if args.spec == "-":
        spec = json.load(sys.stdin)
    else:
        with open(args.spec) as f:
            spec = json.load(f)

    # Load icons
    icons = IconPack(args.icons)

    # Validate
    errors, warnings = validate_spec(spec, icons)

    for w in warnings:
        print(f"  WARN: {w}", file=sys.stderr)

    if errors:
        print(f"\n{len(errors)} validation error(s):", file=sys.stderr)
        for e in errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.validate_only:
        print("Spec is valid.")
        sys.exit(0)

    # Render
    use_html = args.html or args.output.endswith(".html")
    renderer = SvgRenderer(spec, icons)
    result = renderer.render_html() if use_html else renderer.render()

    with open(args.output, "w") as f:
        f.write(result)

    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
