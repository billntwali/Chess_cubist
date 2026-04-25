#!/usr/bin/env python3
"""
generate_blueprint.py — Phase 2 of the Nano Banana Pro pipeline

1. Parses <!-- IMAGE: description --> placeholders from blueprint.svg
2. Searches Tavily for each placeholder to find reference images
3. Downloads images locally
4. Assembles a multimodal prompt describing the hand-drawn style
5. Calls Gemini image generation (Nano Banana Pro)
6. Saves final hand-drawn PNG

Usage:
    export GEMINI_API_KEY=...
    export TAVILY_API_KEY=...       # optional — skipped gracefully if not set
    python tools/generate_blueprint.py
    python tools/generate_blueprint.py --svg path/to/other.svg
"""
import argparse
import base64
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests
from google import genai
from google.genai import types

REPO = Path(__file__).resolve().parents[1]
SVG_PATH = REPO / "assets" / "presentation" / "blueprint.svg"
IMAGES_DIR = REPO / "agent" / "results" / "images"
OUTPUT_PNG = REPO / "assets" / "presentation" / "blueprint_handdrawn.png"

HAND_DRAWN_STYLE_PROMPT = """\
Convert this diagram into a hand-drawn, whiteboard-style illustration:

Style requirements:
- Sketchy, slightly wobbly lines — nothing perfectly straight
- Warm cream or off-white background, like paper
- Three color-coded columns: amber/orange for Planning, green for Building, purple/violet for Runtime
- Rounded boxes with visible hand-drawn strokes
- Clear downward arrows within each column, dashed arrows connecting columns left-to-right
- Casual handwritten font, large enough to read clearly
- Decorative small stars or doodles in the margins
- The overall feel should look like a talented person sketched this on a whiteboard

Diagram content:

Title: "How we used Claude"

PLANNING column (amber/orange):
  Box 1: "CLAUDE.md brief" — Hackathon rubric fed into Claude's context
  Box 2: "Plan iteration" — LLM-PLAN1 → PLAN4, Claude pushes back and refines
  Box 3: "Claude picks best plan" — All team ideas compared, Claude selects and explains
  Box 4: "Per-person Plan Mode" — Each member picks a role, Claude writes their spec

BUILDING column (green):
  Box 1: "5 parallel Claude agents" — One per layer (chips: Rust engine, Eval generator, Backend, Frontend, Tester)
  Box 2: "Claude writes all the code" — Every file written and reviewed with Claude
  Box 3: "Interface contract" — Rust↔Python spec designed with Claude, committed before build started

RUNTIME column (purple):
  Box 1: "① Interpret" — Maps your words into chess concepts
  Box 2: "② Generate" — Writes evaluate(board) live, from scratch
  Box 3: "5-gate validation" — syntax · safety · sanity · determinism · variance
  Box 4: "③ Narrate" — After every move, Claude narrates in the personality's voice

Use the reference images below for style inspiration only — do not copy their content.
"""


# ---------------------------------------------------------------------------
# Step 1: Parse placeholders
# ---------------------------------------------------------------------------

def parse_placeholders(svg_content: str) -> list[str]:
    """Return list of description strings from <!-- IMAGE: ... --> comments."""
    return re.findall(r'<!--\s*IMAGE:\s*(.+?)\s*-->', svg_content)


# ---------------------------------------------------------------------------
# Step 2 + 3: Search Tavily and download images
# ---------------------------------------------------------------------------

def search_tavily(query: str, api_key: str, max_results: int = 3) -> list[str]:
    """Search Tavily and return up to max_results image URLs."""
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query,
            search_depth="basic",
            include_images=True,
            max_results=max_results,
        )
        images = response.get("images", [])
        urls = []
        for img in images:
            url = img if isinstance(img, str) else img.get("url", "")
            if url:
                urls.append(url)
        return urls[:max_results]
    except Exception as e:
        print(f"  Tavily error for '{query}': {e}")
        return []


def download_image(url: str, dest: Path) -> Path | None:
    """Download image at url to dest, return path or None on failure."""
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        suffix = Path(urlparse(url).path).suffix.lower()
        if suffix not in (".jpg", ".jpeg", ".png", ".webp"):
            suffix = ".jpg"
        out = dest.with_suffix(suffix)
        out.write_bytes(resp.content)
        return out
    except Exception as e:
        print(f"  Download failed {url}: {e}")
        return None


def fetch_reference_images(descriptions: list[str], images_dir: Path, tavily_key: str) -> list[Path]:
    """Search and download reference images for all placeholders."""
    images_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, desc in enumerate(descriptions):
        print(f"  Searching: '{desc}'")
        urls = search_tavily(desc, tavily_key)
        for j, url in enumerate(urls[:2]):  # max 2 images per placeholder
            dest = images_dir / f"ref_{i}_{j}"
            path = download_image(url, dest)
            if path:
                paths.append(path)
                print(f"    ↓ {path.name}")
    return paths


# ---------------------------------------------------------------------------
# Step 4: Assemble prompt
# ---------------------------------------------------------------------------

def assemble_prompt(descriptions: list[str]) -> str:
    if descriptions:
        refs = "\n".join(f"- {d}" for d in descriptions)
        suffix = f"\nReference image topics searched: {refs}"
    else:
        suffix = ""
    return HAND_DRAWN_STYLE_PROMPT.strip() + suffix


# ---------------------------------------------------------------------------
# Step 5: Call Gemini
# ---------------------------------------------------------------------------

IMAGE_GEN_MODELS = [
    "gemini-2.0-flash-preview-image-generation",
    "gemini-2.0-flash-exp",
    "gemini-1.5-pro",
]


def _try_generate_content(client, model: str, parts: list) -> bytes | None:
    """Attempt generate_content with IMAGE modality. Returns image bytes or None."""
    response = client.models.generate_content(
        model=model,
        contents=types.Content(parts=parts, role="user"),
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )
    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.mime_type.startswith("image"):
            return part.inline_data.data
    return None


def _try_imagen(client, prompt: str) -> bytes | None:
    """Attempt Imagen 3 text-to-image as final fallback."""
    response = client.models.generate_images(
        model="imagen-3.0-generate-001",
        prompt=prompt[:2000],  # Imagen has a shorter prompt limit
        config=types.GenerateImagesConfig(number_of_images=1),
    )
    if response.generated_images:
        return response.generated_images[0].image.image_bytes
    return None


def call_gemini(prompt: str, image_paths: list[Path], api_key: str) -> bytes | None:
    """Try each image-generation model in order, return first successful image bytes."""
    client = genai.Client(api_key=api_key)

    parts: list = [types.Part.from_text(text=prompt)]
    for path in image_paths:
        if not path.exists():
            continue
        mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        try:
            parts.append(types.Part.from_bytes(data=path.read_bytes(), mime_type=mime))
            print(f"  Attached: {path.name}")
        except Exception as e:
            print(f"  Skipped {path.name}: {e}")

    print(f"  Sending {len(parts)} part(s) to Gemini...")

    for model in IMAGE_GEN_MODELS:
        print(f"  Trying model: {model}")
        try:
            result = _try_generate_content(client, model, parts)
            if result:
                print(f"  ✓ Got image from {model}")
                return result
            print(f"  {model} returned no image, trying next...")
        except Exception as e:
            print(f"  {model} failed: {e}")

    # Final fallback: Imagen (text-only, no reference images)
    print("  Trying Imagen 3 as fallback (text-only)...")
    try:
        result = _try_imagen(client, prompt)
        if result:
            print("  ✓ Got image from Imagen 3")
            return result
    except Exception as e:
        print(f"  Imagen 3 failed: {e}")

    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Nano Banana Pro — SVG → hand-drawn PNG")
    parser.add_argument("--svg", default=str(SVG_PATH), help="Path to SVG blueprint")
    parser.add_argument("--out", default=str(OUTPUT_PNG), help="Output PNG path")
    parser.add_argument("--no-tavily", action="store_true", help="Skip Tavily image search")
    parser.add_argument("--prompt-only", action="store_true", help="Assemble prompt and copy to clipboard, skip API call")
    args = parser.parse_args()

    svg_path = Path(args.svg)
    out_path = Path(args.out)

    print("\n── Nano Banana Pro Pipeline ──\n")

    # Keys
    gemini_key = os.environ.get("GEMINI_API_KEY")
    tavily_key = os.environ.get("TAVILY_API_KEY")
    if not gemini_key and not args.prompt_only:
        print("✗ GEMINI_API_KEY not set — run with --prompt-only to just build the prompt")
        sys.exit(1)

    # 1. Load SVG
    if not svg_path.exists():
        print(f"✗ SVG not found: {svg_path}")
        sys.exit(1)
    svg_content = svg_path.read_text()
    print(f"[1/5] Loaded: {svg_path.name}")

    # 2. Parse placeholders
    descriptions = parse_placeholders(svg_content)
    print(f"[2/5] Placeholders found: {len(descriptions)}")
    for d in descriptions:
        print(f"  · {d}")

    # 3. Search + download images
    image_paths: list[Path] = []
    if descriptions and tavily_key and not args.no_tavily:
        print(f"[3/5] Searching Tavily for reference images...")
        image_paths = fetch_reference_images(descriptions, IMAGES_DIR, tavily_key)
        print(f"[3/5] Downloaded {len(image_paths)} images")
    else:
        reason = "no placeholders" if not descriptions else ("--no-tavily" if args.no_tavily else "TAVILY_API_KEY not set")
        print(f"[3/5] Skipping Tavily ({reason})")

    # 4. Assemble prompt
    prompt = assemble_prompt(descriptions)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    prompt_path = IMAGES_DIR / "prompt.txt"
    prompt_path.write_text(prompt)
    print(f"[4/5] Prompt assembled ({len(prompt)} chars) → {prompt_path}")

    # --prompt-only: copy to clipboard and open file, skip API
    if args.prompt_only:
        import subprocess
        subprocess.run("pbcopy", input=prompt.encode(), check=False)
        print(f"\n✓ Prompt copied to clipboard.")
        print(f"  Paste it into gemini.google.com or aistudio.google.com")
        print(f"  Full prompt also saved to: {prompt_path}")
        return

    # 5. Gemini API
    print(f"[5/5] Calling Gemini image generation...")
    image_bytes = call_gemini(prompt, image_paths, gemini_key)

    if image_bytes:
        out_path.write_bytes(image_bytes)
        print(f"\n✓ Hand-drawn PNG saved → {out_path}")
    else:
        print("\n✗ No image returned. Check model availability and API key quota.")
        sys.exit(1)


if __name__ == "__main__":
    main()
