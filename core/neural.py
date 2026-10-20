"""Red neuronal local y persistente de Igris.

No reemplaza al modelo generativo: aprende una representación neuronal propia de
cada usuario (temas, intenciones y patrones de conversación) y entrega una señal
al sistema de contexto. Los pesos se entrenan localmente con experiencias aprobadas.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from typing import Optional

from sqlalchemy.orm import Session

from core.database import NeuralExperience, NeuralModelState, utcnow

logger = logging.getLogger(__name__)

_DIM = 256
_HIDDEN = 48
_MAX_EXPERIENCES = 500
_TOKEN_RE = re.compile(r"[\wáéíóúñü]{2,}", re.I)


def _features(text: str) -> list[float]:
    values = [0.0] * _DIM
    tokens = _TOKEN_RE.findall((text or "").lower())
    if not tokens:
        return values
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=4).digest()
        values[int.from_bytes(digest, "big") % _DIM] += 1.0
    scale = max(values) or 1.0
    return [min(1.0, value / scale) for value in values]


def _state_row(db: Session, user_id: int) -> Optional[NeuralModelState]:
    return db.query(NeuralModelState).filter(NeuralModelState.user_id == user_id).first()


def _torch():
    try:
        import torch
        import torch.nn as nn
        return torch, nn
    except Exception:
        return None, None


def _new_model(torch, nn, labels: list[str]):
    model = nn.Sequential(nn.Linear(_DIM, _HIDDEN), nn.ReLU(), nn.Linear(_HIDDEN, len(labels)))
    return model


def _serialize(model, labels: list[str], torch) -> str:
    return json.dumps({
        "labels": labels,
        "dimension": _DIM,
        "hidden": _HIDDEN,
        "weights": {key: value.detach().cpu().tolist() for key, value in model.state_dict().items()},
    }, ensure_ascii=False, separators=(",", ":"))


def _load_model(payload: dict, torch, nn):
    labels = [str(label) for label in payload.get("labels", [])]
    if not labels or payload.get("dimension") != _DIM:
        return None, labels
    model = _new_model(torch, nn, labels)
    try:
        state = {key: torch.tensor(value, dtype=torch.float32) for key, value in payload["weights"].items()}
        model.load_state_dict(state)
        model.eval()
        return model, labels
    except Exception:
        return None, labels


def train_user_model(db: Session, user_id: Optional[int], *, epochs: int = 24) -> dict:
    """Entrena localmente el MLP del usuario con sus experiencias aprobadas."""
    if not user_id:
        return {"trained": False, "reason": "sin_usuario"}
    torch, nn = _torch()
    if torch is None:
        return {"trained": False, "reason": "torch_no_disponible"}
    rows = db.query(NeuralExperience).filter(
        NeuralExperience.user_id == user_id,
        NeuralExperience.approved.is_(True),
    ).order_by(NeuralExperience.created_at.desc()).limit(_MAX_EXPERIENCES).all()
    labels = sorted({row.label for row in rows})
    if len(rows) < 2 or len(labels) < 1:
        return {"trained": False, "samples": len(rows), "reason": "faltan_experiencias"}
    label_index = {label: index for index, label in enumerate(labels)}
    x = torch.tensor([_features(row.text) for row in rows], dtype=torch.float32)
    y = torch.tensor([label_index[row.label] for row in rows], dtype=torch.long)
    state_row = _state_row(db, user_id)
    model = None
    if state_row is not None:
        try:
            model, old_labels = _load_model(json.loads(state_row.model_json), torch, nn)
            if old_labels != labels:
                model = None
        except Exception:
            model = None
    model = model or _new_model(torch, nn, labels)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.008)
    loss_fn = nn.CrossEntropyLoss()
    model.train()
    for _ in range(max(1, min(epochs, 60))):
        optimizer.zero_grad()
        loss = loss_fn(model(x), y)
        loss.backward()
        optimizer.step()
    model.eval()
    with torch.no_grad():
        accuracy = int((model(x).argmax(dim=1) == y).float().mean().item() * 100)
    payload = _serialize(model, labels, torch)
    if state_row is None:
        state_row = NeuralModelState(user_id=user_id, model_json=payload)
        db.add(state_row)
    else:
        state_row.model_json = payload
        state_row.updated_at = utcnow()
    state_row.trained_samples = len(rows)
    state_row.accuracy = accuracy
    state_row.version = (state_row.version or 0) + 1
    db.commit()
    return {"trained": True, "samples": len(rows), "labels": labels, "accuracy": accuracy, "version": state_row.version}


def record_experience(
    db: Session,
    user_id: Optional[int],
    text: str,
    labels: list[str],
    *,
    response: Optional[str] = None,
    source: str = "chat",
    train: bool = True,
) -> int:
    """Registra ejemplos conservadores y activa el autoaprendizaje local."""
    if not user_id or not (text or '').strip():
        return 0
    clean = re.sub(r"\s+", " ", text.strip())[:4000]
    clean_labels = list(dict.fromkeys(label.strip().lower()[:64] for label in labels if label and label.strip()))
    created = 0
    for label in clean_labels[:8]:
        exists = db.query(NeuralExperience).filter(
            NeuralExperience.user_id == user_id,
            NeuralExperience.text == clean,
            NeuralExperience.label == label,
        ).first()
        if exists is None:
            db.add(NeuralExperience(user_id=user_id, text=clean, label=label, response=response, source=source))
            created += 1
    if created:
        db.commit()
        # El aprendizaje es automático, pero acotado: se reentrena al crear el
        # primer ejemplo y después cada cinco ejemplos nuevos. Así no bloquea
        # cada turno de chat mientras conserva adaptación incremental.
        total = db.query(NeuralExperience).filter(NeuralExperience.user_id == user_id).count()
        if train and (total <= 2 or total % 5 == 0):
            try:
                train_user_model(db, user_id)
            except Exception:
                logger.exception("No se pudo entrenar la red neuronal local del usuario %s", user_id)
    return created


def predict_context(db: Session, user_id: Optional[int], text: str) -> str:
    """Devuelve la predicción neuronal para incluirla como señal contextual."""
    if not user_id or not text:
        return ""
    row = _state_row(db, user_id)
    if row is None:
        return ""
    torch, nn = _torch()
    if torch is None:
        return ""
    try:
        payload = json.loads(row.model_json)
        model, labels = _load_model(payload, torch, nn)
        if model is None:
            return ""
        with torch.no_grad():
            probabilities = torch.softmax(model(torch.tensor([_features(text)], dtype=torch.float32)), dim=1)[0]
            index = int(probabilities.argmax().item())
            confidence = float(probabilities[index].item())
        if confidence < 0.45:
            return ""
        return f"Señal neuronal local de Igris: tema/intención probable «{labels[index]}» ({confidence:.0%}). Úsala como pista, no como hecho."
    except Exception:
        logger.exception("No se pudo inferir con la red neuronal local")
        return ""


def model_status(db: Session, user_id: Optional[int]) -> dict:
    row = _state_row(db, user_id) if user_id else None
    count = db.query(NeuralExperience).filter(NeuralExperience.user_id == user_id).count() if user_id else 0
    return {
        "own_neural_network": bool(row),
        "auto_learning": True,
        "trained": bool(row),
        "samples": count,
        "trained_samples": row.trained_samples if row else 0,
        "accuracy": row.accuracy if row else 0,
        "version": row.version if row else 0,
        "backend": "PyTorch MLP local" if _torch()[0] is not None else "no disponible",
    }


__all__ = ["record_experience", "train_user_model", "predict_context", "model_status"]
