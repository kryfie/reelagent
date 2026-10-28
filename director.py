"""ReelAgent Director: predictable editing decisions, no paid inference.

Captions produced by optional browser-side Florence-2 are merely hints. The
backend NEVER trusts them as authoritative product or marketing claims.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

VALID_ROLES = {'product', 'action', 'people', 'place', 'detail', 'other'}
ROLES = {
    'action': ('pour', 'pouring', 'making', 'preparing', 'cook', 'serve', 'serving', 'cut', 'stir', 'mix', 'fry', 'steam', 'nalew', 'przygot'),
    'product': ('food', 'dish', 'dessert', 'pastry', 'churro', 'coffee', 'cup', 'cake', 'plate', 'meal', 'drink', 'ciasto', 'kawa', 'produkt'),
    'people': ('person', 'people', 'man', 'woman', 'customer', 'barista', 'chef', 'hand', 'ludzi', 'osoba'),
    'place': ('room', 'building', 'cafe', 'restaurant', 'interior', 'shop', 'store', 'garden', 'wnętrz', 'kawiarn'),
    'detail': ('close-up', 'closeup', 'macro', 'detail', 'texture', 'detal'),
}


def role_from_caption(description: str) -> str:
    s = re.sub(r'[^\w\s-]', ' ', description.lower())[:350]
    for role, words in ROLES.items():
        if any(re.search(r'(?<!\w)' + re.escape(w), s) for w in words):
            return role
    return 'other'


def plan_scenes(media: list[dict[str, Any]], *, style: str, length: int,
                variant: int = 0, auto_director: bool = False) -> list[dict[str, Any]]:
    """Return scene plan with ordering + durations + camera behavior.

    Deterministic for same input and variant. Individual captions remain bound
    to their original input media. No random fabricated text, no generative video.
    """
    n = len(media)
    indices = list(range(n))
    if auto_director:
        # Choose high-impact authentic motion as hook; otherwise use detailed product.
        def rank(i: int):
            m = media[i]
            role = m.get('role') or role_from_caption(m.get('ai_description', ''))
            if role not in VALID_ROLES: role = 'other'
            has_motion = m.get('type') == 'video'
            weights = {
                'film': {'product': 22, 'action': 24, 'detail': 20, 'people': 12, 'place': 8, 'other': 4},
                'dynamic': {'action': 28, 'product': 20, 'detail': 16, 'people': 12, 'place': 8, 'other': 4},
                'story': {'action': 25, 'product': 19, 'people': 15, 'detail': 13, 'place': 8, 'other': 4},
            }[style]
            return weights[role] + (14 if has_motion else 0)
        first = max(indices, key=lambda i: (rank(i), -i))
        others = [i for i in indices if i != first]
        # Keep same inputs but rotate the supporting montage in subsequent variants.
        # This is a simple, intentional transformation, not arbitrary reshuffling.
        if others and variant % 3 == 1: others = others[1:] + others[:1]
        elif others and variant % 3 == 2: others = list(reversed(others))
        indices = [first] + others

    total = float(length) - 1.8
    weights = []
    for pos, source in enumerate(indices):
        m = media[source]
        w = 1.0
        if m['type'] == 'video': w *= 1.12
        if pos == 0: w *= 1.15
        if style == 'dynamic': w *= (0.94 if pos % 2 else 1.07)
        if style == 'story' and pos == len(indices)-1: w *= 1.13
        weights.append(w)
    norm = sum(weights)
    durations = [total * x / norm for x in weights]
    # Exact sum after rounding; last clip absorbs fractional rounding.
    durations = [round(x, 2) for x in durations]
    durations[-1] = round(total - sum(durations[:-1]), 2)
    camera = ['zoom_in', 'pan_right', 'zoom_out', 'pan_left']
    return [{
        'index': source,
        'duration': durations[pos],
        'motion': camera[(pos + variant) % len(camera)],
        'source_type': media[source]['type'],
    } for pos, source in enumerate(indices)]
