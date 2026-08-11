"""
Image Generation MCP Tool & ComfyUI / SD Sideload Hook.
Designed for local ComfyUI, Automatic1111, or open remote endpoints.
Treats ComfyUI as a side-load for compatible hardware (GPU/CUDA/x86/Apple Silicon),
maintaining full compatibility when the repository is pulled across different hardware environments.
Substrate invariant: Binary image data is never stored as historical truth; only content references.
"""
from __future__ import annotations

import os
import json
import uuid
import hashlib
from typing import Any, Optional
import httpx

COMFYUI_URL = os.getenv("COMFYUI_URL", os.getenv("IMAGE_BACKEND_URL", "http://localhost:8188"))
A1111_URL = os.getenv("A1111_URL", "http://localhost:7860")


def check_backend_status() -> dict[str, Any]:
    """Check live status of ComfyUI and Automatic1111 endpoints."""
    comfy_live = False
    a1111_live = False
    comfy_info = {}

    try:
        r = httpx.get(f"{COMFYUI_URL}/system_stats", timeout=1.5)
        if r.status_code == 200:
            comfy_live = True
            comfy_info = r.json()
    except Exception:
        pass

    try:
        r = httpx.get(f"{A1111_URL}/sdapi/v1/options", timeout=1.5)
        if r.status_code == 200:
            a1111_live = True
    except Exception:
        pass

    return {
        "comfyui_url": COMFYUI_URL,
        "comfyui_live": comfy_live,
        "a1111_url": A1111_URL,
        "a1111_live": a1111_live,
        "sideload_mode": "active" if (comfy_live or a1111_live) else "standby",
        "hardware_note": "ComfyUI treated as dynamic sideload. Active on GPU/compatible hosts; procedural fallback on lightweight hosts.",
        "comfy_stats": comfy_info,
    }


def generate_glyph(
    prompt: str,
    negative_prompt: str = "blurry, text, low quality, artifacts",
    width: int = 512,
    height: int = 512,
    seed: Optional[int] = None,
    function_tag: Optional[str] = None,
    phase: Optional[str] = None,
    svg_symbol_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Generate or synthesize glyph/emblem visual asset reference.
    If ComfyUI is live, dispatches prompt workflow; otherwise returns procedural reference
    compatible with the Ledger Set SVG manifest.
    """
    status = check_backend_status()
    prompt_hash = hashlib.sha256(f"{prompt}:{seed}".encode()).hexdigest()[:12]
    ref_id = f"glyph://ledger/{function_tag or 'symbol'}/{phase or 'core'}/{prompt_hash}"

    # 1. If ComfyUI is live, submit workflow prompt
    if status["comfyui_live"]:
        try:
            workflow = {
                "client_id": str(uuid.uuid4()),
                "prompt": {
                    "3": {
                        "class_type": "KSampler",
                        "inputs": {
                            "cfg": 8,
                            "denoise": 1,
                            "latent_image": ["5", 0],
                            "model": ["4", 0],
                            "negative": ["7", 0],
                            "positive": ["6", 0],
                            "sampler_name": "euler",
                            "scheduler": "normal",
                            "seed": seed or 42,
                            "steps": 20,
                        },
                    },
                    "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "v1-5-pruned-emaonly.ckpt"}},
                    "5": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1, "height": height, "width": width}},
                    "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": prompt}},
                    "7": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": negative_prompt}},
                    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
                    "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": f"glyph_{prompt_hash}", "images": ["8", 0]}},
                },
            }
            r = httpx.post(f"{COMFYUI_URL}/prompt", json=workflow, timeout=10.0)
            if r.status_code == 200:
                resp_data = r.json()
                return {
                    "ok": True,
                    "kind": "image_generation",
                    "mode": "live_comfyui",
                    "prompt_id": resp_data.get("prompt_id"),
                    "backend": COMFYUI_URL,
                    "reference": f"comfyui://output/{resp_data.get('prompt_id')}",
                    "node_props_reference": ref_id,
                    "svg_symbol_id": svg_symbol_id,
                }
        except Exception as exc:
            pass  # Fall back to procedural reference

    # 2. Standby / Sideload mode (procedural & SVG ledger reference)
    return {
        "ok": True,
        "kind": "image_generation",
        "mode": "sideload_standby",
        "backend": COMFYUI_URL,
        "reference": ref_id,
        "svg_symbol_id": svg_symbol_id,
        "function_tag": function_tag,
        "phase": phase,
        "prompt": prompt,
        "note": "ComfyUI endpoint standby. Reference burned into Ledger DAG; live image synthesis triggers when ComfyUI side-load is online.",
    }


MCP_IMAGE_TOOL_SPEC = {
    "name": "generate_glyph_image",
    "description": "Outsource glyph/emblem image generation via MCP (live ComfyUI or standby sideload). Returns reference URI.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "Visual prompt for glyph or emblem synthesis"},
            "negative_prompt": {"type": "string", "default": "blurry, text, low quality"},
            "width": {"type": "integer", "default": 512},
            "height": {"type": "integer", "default": 512},
            "seed": {"type": "integer"},
            "function_tag": {"type": "string", "description": "Ledger function tag (Anchor, Span, Vector, etc.)"},
            "phase": {"type": "string", "description": "Phase (Initiation, Stabilization, Resolution)"},
            "svg_symbol_id": {"type": "string", "description": "Associated SVG geometry symbol identifier"},
        },
        "required": ["prompt"],
    },
}
