"""Failure clustering. Spec §8a.

Embeds failure outputs, runs KMeans, then asks the LLM for a short label per cluster.
"""
from __future__ import annotations

from collections import Counter
from typing import Iterable

import numpy as np
from sklearn.cluster import KMeans

from ..llm.clients import chat_complete, embed


_LABEL_PROMPT = (
    "Here are {n} AI agent failure outputs. In one short phrase (max 8 words), "
    "describe what they have in common. Return ONLY the phrase."
)


def _label_cluster(samples: list[str]) -> str:
    user = "\n\n---\n\n".join(s[:400] for s in samples[:5])
    raw, _ = chat_complete(
        [
            {"role": "system", "content": _LABEL_PROMPT.format(n=len(samples))},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
        max_tokens=40,
    )
    label = raw.strip().strip('"').strip("'")
    return " ".join(label.split()[:8]) or "unlabeled failure cluster"


def cluster_failures(
    failures: list[dict],
) -> list[dict]:
    """Inputs: list of {"id": str, "input": str, "output": str, "failure_reason": str | None}.

    Returns a list of clusters:
        {"label", "count", "example_scenario_id", "example_input", "example_output"}
    """
    if not failures:
        return []

    if len(failures) <= 2:
        # Not worth clustering — just return one bucket per failure with the reason as label.
        return [
            {
                "label": (f.get("failure_reason") or "failure")[:64],
                "count": 1,
                "example_scenario_id": f.get("id"),
                "example_input": f["input"],
                "example_output": f["output"],
            }
            for f in failures
        ]

    outputs = [f["output"] or "" for f in failures]
    try:
        vectors = embed(outputs)
    except Exception:
        # Fallback: bucket by failure_reason string if embeddings fail.
        return _fallback_by_reason(failures)

    n_clusters = min(3, len(failures))
    matrix = np.array(vectors)
    km = KMeans(n_clusters=n_clusters, n_init=10, random_state=42).fit(matrix)
    labels = km.labels_

    clusters: list[dict] = []
    for cid in range(n_clusters):
        idxs = [i for i, l in enumerate(labels) if l == cid]
        if not idxs:
            continue
        # Representative = closest to centroid.
        center = km.cluster_centers_[cid]
        dists = [(i, float(np.linalg.norm(matrix[i] - center))) for i in idxs]
        dists.sort(key=lambda x: x[1])
        rep_idx = dists[0][0]
        samples = [failures[i]["output"] for i in idxs[:5]]
        label = _label_cluster(samples)
        clusters.append(
            {
                "label": label,
                "count": len(idxs),
                "example_scenario_id": failures[rep_idx].get("id"),
                "example_input": failures[rep_idx]["input"],
                "example_output": failures[rep_idx]["output"],
            }
        )
    clusters.sort(key=lambda c: c["count"], reverse=True)
    return clusters


def _fallback_by_reason(failures: list[dict]) -> list[dict]:
    counter = Counter((f.get("failure_reason") or "unlabeled failure")[:64] for f in failures)
    out = []
    for label, count in counter.most_common(3):
        example = next(f for f in failures if (f.get("failure_reason") or "unlabeled failure")[:64] == label)
        out.append(
            {
                "label": label,
                "count": count,
                "example_scenario_id": example.get("id"),
                "example_input": example["input"],
                "example_output": example["output"],
            }
        )
    return out
