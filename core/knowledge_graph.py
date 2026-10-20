"""Operaciones básicas para la memoria relacional de Igris.

Este módulo no sustituye todavía la memoria textual: permite construir el grafo
progresivamente y conservar el origen, la confianza y la vigencia de cada dato.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import json
import logging
import os
import re
import threading
from typing import Optional

from dataclasses import dataclass

logger = logging.getLogger(__name__)
_GRAPH_BACKFILL_INFLIGHT: set[int] = set()
_GRAPH_BACKFILL_LOCK = threading.Lock()
_GRAPH_EMBEDDINGS_ENABLED = os.environ.get("IGRIS_MEMORY_EMBEDDINGS_ENABLED", "false").lower() in {"1", "true", "yes", "on"}

from sqlalchemy.orm import Session

from core.database import KnowledgeNode, KnowledgeRelation, utcnow


def _embedding_for(text: str) -> Optional[list[float]]:
    """Reutiliza el proveedor opcional de embeddings de la memoria textual."""
    from core.memory import _embedding_for as memory_embedding_for
    return memory_embedding_for(text)


def _decode_embedding(value: Optional[str]) -> Optional[list[float]]:
    if not value:
        return None
    try:
        decoded = json.loads(value)
        return [float(item) for item in decoded] if isinstance(decoded, list) else None
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _cosine_similarity(left: Optional[list[float]], right: Optional[list[float]]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    left_norm = sum(value * value for value in left) ** 0.5
    right_norm = sum(value * value for value in right) ** 0.5
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


def _bounded(value: int, default: int = 50) -> int:
    return max(0, min(100, int(value if value is not None else default)))


def _currently_valid(entity) -> bool:
    """Comprueba vigencia temporal sin ocultar datos históricos archivados."""
    now = utcnow()
    return (
        entity.status == "active"
        and (entity.valid_from is None or entity.valid_from <= now)
        and (entity.valid_until is None or entity.valid_until >= now)
    )


def upsert_node(
    db: Session,
    user_id: int,
    node_type: str,
    name: str,
    *,
    description: Optional[str] = None,
    confidence: int = 50,
    importance: int = 1,
    source: str = "chat",
    source_ref: Optional[str] = None,
    status: str = "active",
    valid_from: Optional[datetime] = None,
    valid_until: Optional[datetime] = None,
) -> KnowledgeNode:
    """Crea una entidad o actualiza la existente del mismo usuario y nombre."""
    clean_type = node_type.strip().lower()[:32]
    clean_name = name.strip()[:255]
    if not user_id or not clean_type or not clean_name:
        raise ValueError("user_id, node_type y name son obligatorios")

    node = db.query(KnowledgeNode).filter(
        KnowledgeNode.user_id == user_id,
        KnowledgeNode.node_type == clean_type,
        KnowledgeNode.name == clean_name,
    ).first()
    if node is None:
        node = KnowledgeNode(
            user_id=user_id,
            node_type=clean_type,
            name=clean_name,
        )
        db.add(node)

    node.description = description if description is not None else node.description
    node.confidence = _bounded(confidence, node.confidence or 50)
    node.importance = max(1, min(100, int(importance)))
    node.source = source[:32]
    node.source_ref = source_ref[:255] if source_ref else node.source_ref
    node.status = status[:20]
    node.valid_from = valid_from if valid_from is not None else node.valid_from
    node.valid_until = valid_until if valid_until is not None else node.valid_until
    node.updated_at = utcnow()
    return node


def _backfill_node_embeddings(user_id: int, limit: int = 24) -> None:
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        rows = db.query(KnowledgeNode).filter(
            KnowledgeNode.user_id == user_id,
            KnowledgeNode.status == "active",
        ).order_by(KnowledgeNode.updated_at.desc(), KnowledgeNode.id.desc()).limit(limit).all()
        changed = False
        for node in rows:
            if node.embedding:
                continue
            vector = _embedding_for(f"{node.node_type}: {node.name}. {node.description or ''}")
            if vector is None:
                break
            node.embedding = json.dumps(vector, separators=(",", ":"))
            changed = True
        if changed:
            db.commit()
    except Exception as exc:
        logger.warning("No se pudieron calcular embeddings del grafo: %s", exc)
        db.rollback()
    finally:
        db.close()


def schedule_node_embedding_backfill(user_id: Optional[int], limit: int = 24) -> None:
    if not user_id or not _GRAPH_EMBEDDINGS_ENABLED:
        return
    with _GRAPH_BACKFILL_LOCK:
        if user_id in _GRAPH_BACKFILL_INFLIGHT:
            return
        _GRAPH_BACKFILL_INFLIGHT.add(user_id)

    def run() -> None:
        try:
            _backfill_node_embeddings(user_id, limit)
        finally:
            with _GRAPH_BACKFILL_LOCK:
                _GRAPH_BACKFILL_INFLIGHT.discard(user_id)

    threading.Thread(target=run, name=f"graph-emb-{user_id}", daemon=True).start()


def upsert_relation(
    db: Session,
    user_id: int,
    from_node: KnowledgeNode,
    relation_type: str,
    to_node: KnowledgeNode,
    *,
    confidence: int = 50,
    source: str = "chat",
    source_ref: Optional[str] = None,
    valid_from: Optional[datetime] = None,
    valid_until: Optional[datetime] = None,
) -> KnowledgeRelation:
    """Crea o refuerza una conexión tipada entre dos nodos del usuario."""
    if from_node.user_id != user_id or to_node.user_id != user_id:
        raise ValueError("Los nodos deben pertenecer al usuario de la relación")
    # Permite relacionar dos nodos recién creados en la misma transacción.
    db.flush()
    if from_node.id == to_node.id:
        raise ValueError("Una relación no puede conectar un nodo consigo mismo")

    relation_name = relation_type.strip().lower()[:64]
    relation = db.query(KnowledgeRelation).filter(
        KnowledgeRelation.user_id == user_id,
        KnowledgeRelation.from_node_id == from_node.id,
        KnowledgeRelation.to_node_id == to_node.id,
        KnowledgeRelation.relation_type == relation_name,
    ).first()
    if relation is None:
        relation = KnowledgeRelation(
            user_id=user_id,
            from_node_id=from_node.id,
            to_node_id=to_node.id,
            relation_type=relation_name or "related_to",
            weight=1,
        )
        db.add(relation)
    else:
        relation.weight = min(100, relation.weight + 1)

    relation.confidence = _bounded(confidence, relation.confidence or 50)
    relation.source = source[:32]
    relation.source_ref = source_ref[:255] if source_ref else relation.source_ref
    relation.status = "active"
    relation.valid_from = valid_from if valid_from is not None else relation.valid_from
    relation.valid_until = valid_until if valid_until is not None else relation.valid_until
    relation.last_confirmed_at = utcnow()
    relation.updated_at = utcnow()
    return relation


@dataclass(frozen=True)
class GraphFact:
    """Hecho explícito extraído del mensaje del propio usuario."""
    subject_type: str
    subject: str
    relation: str
    object_type: str
    object: str


_FACT_PATTERNS = (
    (re.compile(r"^me llamo\s+(.+)$", re.I), "person", "name", "person", "user"),
    (re.compile(r"^(?:prefiero|me gusta)\s+(.+)$", re.I), "person", "prefers", "preference", "user"),
    (re.compile(r"^no me gusta\s+(.+)$", re.I), "person", "dislikes", "preference", "user"),
    (re.compile(r"^(?:trabajo en|estoy trabajando en)\s+(.+)$", re.I), "person", "works_on", "project", "user"),
    (re.compile(r"^(?:vivo en|soy de)\s+(.+)$", re.I), "person", "lives_in", "place", "user"),
    (re.compile(r"^(?:mi objetivo es|mi objetivo:)\s+(.+)$", re.I), "person", "has_goal", "goal", "user"),
    (re.compile(r"^(?:el proyecto|proyecto)\s+(.+?)\s+(?:usa|utiliza)\s+(.+)$", re.I), "project", "uses", "technology", "project"),
)


def extract_explicit_facts(user_text: str) -> list[GraphFact]:
    """Extrae solo afirmaciones directas con patrones pequeños y auditables.

    No interpreta textos de terceros ni inventa entidades. El usuario se representa
    con el nodo estable ``user``; las futuras extracciones de modelo podrán ampliar
    esta lista con una fuente y confianza distintas.
    """
    text = re.sub(r"\s+", " ", (user_text or "")).strip().rstrip(".!?")
    if len(text) < 4 or text.lower().startswith(("olvida que", "borra de tu memoria")):
        return []
    facts: list[GraphFact] = []
    for pattern, subject_type, relation, object_type, _ in _FACT_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        groups = match.groups()
        if len(groups) == 1:
            facts.append(GraphFact(subject_type, "user", relation, object_type, groups[0].strip()))
        else:
            facts.append(GraphFact(subject_type, groups[0].strip(), relation, object_type, groups[1].strip()))
        break
    return [fact for fact in facts if 2 <= len(fact.object) <= 255]


def _apply_corrections(db: Session, user_id: int, user_text: str) -> bool:
    """Archiva relaciones contradichas por una corrección explícita."""
    text = re.sub(r"\s+", " ", (user_text or "")).strip().rstrip(".!?")
    match = re.match(r"^(?:ya no|dejé de) (trabajar en|estar trabajando en|preferir|gustar)\s+(.+)$", text, re.I)
    if not match:
        return False
    relation_type = "works_on" if "trabaj" in match.group(1).lower() else "prefers"
    target_name = match.group(2).strip()
    relations = db.query(KnowledgeRelation).join(
        KnowledgeNode, KnowledgeRelation.to_node_id == KnowledgeNode.id,
    ).filter(
        KnowledgeRelation.user_id == user_id,
        KnowledgeRelation.status == "active",
        KnowledgeRelation.relation_type == relation_type,
        KnowledgeNode.name == target_name,
    ).all()
    changed = False
    for relation in relations:
        relation.status = "superseded"
        relation.updated_at = utcnow()
        changed = True
    return changed


def _supersede_conflicting_relations(
    db: Session,
    user_id: int,
    subject: KnowledgeNode,
    relation_type: str,
    target: KnowledgeNode,
) -> bool:
    """Conserva un solo valor activo para relaciones funcionalmente exclusivas."""
    exclusive = {"works_on", "prefers", "lives_in", "has_goal", "name"}
    if relation_type not in exclusive or subject.id is None or target.id is None:
        return False
    rows = db.query(KnowledgeRelation).filter(
        KnowledgeRelation.user_id == user_id,
        KnowledgeRelation.from_node_id == subject.id,
        KnowledgeRelation.relation_type == relation_type,
        KnowledgeRelation.status == "active",
        KnowledgeRelation.to_node_id != target.id,
    ).all()
    changed = False
    for relation in rows:
        relation.status = "superseded"
        relation.updated_at = utcnow()
        changed = True
    return changed


def remember_explicit_facts(
    db: Session,
    user_id: int,
    user_text: str,
    *,
    source: str = "chat",
    source_ref: Optional[str] = None,
) -> int:
    """Persiste hechos explícitos y correcciones sin tocar UserMemory."""
    corrected = _apply_corrections(db, user_id, user_text)
    facts = extract_explicit_facts(user_text)
    for fact in facts:
        subject = upsert_node(db, user_id, fact.subject_type, fact.subject, confidence=95, importance=3, source=source, source_ref=source_ref)
        target = upsert_node(db, user_id, fact.object_type, fact.object, confidence=95, importance=3, source=source, source_ref=source_ref)
        _supersede_conflicting_relations(db, user_id, subject, fact.relation, target)
        upsert_relation(db, user_id, subject, fact.relation, target, confidence=95, source=source, source_ref=source_ref)
    if facts or corrected:
        db.commit()
        schedule_node_embedding_backfill(user_id)
    return len(facts)


def graph_context(db: Session, user_id: Optional[int], query: Optional[str] = None, limit: int = 8) -> list[str]:
    """Devuelve conexiones activas relevantes, incluyendo un segundo salto acotado."""
    if not user_id or limit <= 0:
        return []
    rows = db.query(KnowledgeRelation).filter(
        KnowledgeRelation.user_id == user_id,
        KnowledgeRelation.status == "active",
    ).order_by(
        KnowledgeRelation.confidence.desc(),
        KnowledgeRelation.weight.desc(),
        KnowledgeRelation.updated_at.desc(),
    ).limit(500).all()
    active_rows = [
        relation for relation in rows
        if relation.from_node and relation.to_node
        and _currently_valid(relation)
        and _currently_valid(relation.from_node) and _currently_valid(relation.to_node)
    ]
    query_vector = _embedding_for(query.strip()) if query and query.strip() else None
    tokens = {token.lower() for token in re.findall(r"[\wáéíóúñü]{3,}", query or "")}

    def relevance(relation: KnowledgeRelation) -> tuple[float, int, int]:
        names = {relation.from_node.name.lower(), relation.to_node.name.lower()}
        lexical = 1.0 if tokens & names else 0.0
        semantic = max(
            _cosine_similarity(query_vector, _decode_embedding(relation.from_node.embedding)),
            _cosine_similarity(query_vector, _decode_embedding(relation.to_node.embedding)),
        ) if query_vector else 0.0
        return (max(lexical, semantic), relation.confidence, relation.weight)

    ranked = sorted(active_rows, key=relevance, reverse=True)
    primary_limit = min(limit, max(1, limit // 2)) if query else limit
    selected = ranked[:primary_limit]
    # Si hay una conexión relevante, incorpora sus relaciones adyacentes como contexto
    # de segundo salto, sin repetir relaciones ni superar el límite solicitado.
    anchor_ids = {node_id for relation in selected for node_id in (relation.from_node_id, relation.to_node_id)}
    if anchor_ids and len(selected) < limit:
        adjacent = [
            relation for relation in active_rows
            if relation not in selected
            and (relation.from_node_id in anchor_ids or relation.to_node_id in anchor_ids)
        ]
        selected.extend(sorted(adjacent, key=relevance, reverse=True)[:limit - len(selected)])
    return [
        f"{relation.from_node.name} —{relation.relation_type}→ {relation.to_node.name}"
        for relation in selected
    ]


def search_graph_nodes(db: Session, user_id: Optional[int], query: str, limit: int = 20) -> list[dict]:
    """Busca entidades activas del usuario por nombre o descripción."""
    if not user_id or not query or limit <= 0:
        return []
    clean_query = query.strip()[:120]
    if not clean_query:
        return []
    pattern = f"%{clean_query}%"
    rows = db.query(KnowledgeNode).filter(
        KnowledgeNode.user_id == user_id,
        KnowledgeNode.status == "active",
        (KnowledgeNode.valid_from.is_(None) | (KnowledgeNode.valid_from <= utcnow())),
        (KnowledgeNode.valid_until.is_(None) | (KnowledgeNode.valid_until >= utcnow())),
        (KnowledgeNode.name.ilike(pattern) | KnowledgeNode.description.ilike(pattern)),
    ).order_by(
        KnowledgeNode.importance.desc(),
        KnowledgeNode.confidence.desc(),
        KnowledgeNode.updated_at.desc(),
    ).limit(min(limit, 100)).all()
    return [
        {"id": node.id, "type": node.node_type, "name": node.name, "description": node.description}
        for node in rows
    ]


def graph_neighbors(db: Session, user_id: Optional[int], node_id: int, limit: int = 20) -> list[dict]:
    """Devuelve vecinos activos del nodo, siempre dentro del usuario autenticado."""
    if not user_id or not node_id:
        return []
    node = db.query(KnowledgeNode).filter(
        KnowledgeNode.id == node_id,
        KnowledgeNode.user_id == user_id,
        KnowledgeNode.status == "active",
        (KnowledgeNode.valid_from.is_(None) | (KnowledgeNode.valid_from <= utcnow())),
        (KnowledgeNode.valid_until.is_(None) | (KnowledgeNode.valid_until >= utcnow())),
    ).first()
    if node is None:
        return []
    rows = db.query(KnowledgeRelation).filter(
        KnowledgeRelation.user_id == user_id,
        KnowledgeRelation.status == "active",
        (KnowledgeRelation.from_node_id == node_id) | (KnowledgeRelation.to_node_id == node_id),
    ).order_by(KnowledgeRelation.weight.desc(), KnowledgeRelation.confidence.desc()).limit(limit).all()
    result = []
    for relation in rows:
        neighbor = relation.to_node if relation.from_node_id == node_id else relation.from_node
        if neighbor is None or neighbor.status != "active":
            continue
        result.append({
            "relation_id": relation.id,
            "node_id": neighbor.id,
            "node_type": neighbor.node_type,
            "name": neighbor.name,
            "relation": relation.relation_type,
            "direction": "outgoing" if relation.from_node_id == node_id else "incoming",
            "confidence": relation.confidence,
            "weight": relation.weight,
        })
    return result


def set_graph_relation_status(db: Session, user_id: Optional[int], relation_id: int, status: str) -> bool:
    """Archiva o restaura una relación propia sin eliminar su historial."""
    if not user_id or not relation_id or status not in {"active", "archived"}:
        return False
    relation = db.query(KnowledgeRelation).filter(
        KnowledgeRelation.id == relation_id,
        KnowledgeRelation.user_id == user_id,
    ).first()
    if relation is None or relation.status == "superseded":
        return False
    if relation.status == status:
        return True
    relation.status = status
    relation.updated_at = utcnow()
    if status == "active":
        relation.last_confirmed_at = relation.last_confirmed_at or relation.updated_at
    db.commit()
    return True


def confirm_graph_relation(db: Session, user_id: Optional[int], relation_id: int) -> bool:
    """Confirma una relación propia y refuerza su peso sin superar 100."""
    if not user_id or not relation_id:
        return False
    relation = db.query(KnowledgeRelation).filter(
        KnowledgeRelation.id == relation_id,
        KnowledgeRelation.user_id == user_id,
        KnowledgeRelation.status == "active",
    ).first()
    if relation is None:
        return False
    relation.last_confirmed_at = utcnow()
    relation.updated_at = relation.last_confirmed_at
    relation.weight = min(100, max(1, relation.weight or 1) + 1)
    relation.confidence = min(100, max(0, relation.confidence or 0) + 1)
    db.commit()
    return True


def stale_graph_relations(db: Session, user_id: Optional[int], days: int = 180, limit: int = 100) -> list[dict]:
    """Lista relaciones activas sin confirmación reciente para revisión del usuario."""
    if not user_id or days <= 0 or limit <= 0:
        return []
    cutoff = utcnow() - timedelta(days=min(days, 3650))
    rows = db.query(KnowledgeRelation).filter(
        KnowledgeRelation.user_id == user_id,
        KnowledgeRelation.status == "active",
        ((KnowledgeRelation.last_confirmed_at.is_(None) & (KnowledgeRelation.updated_at < cutoff)) |
         ((KnowledgeRelation.last_confirmed_at.isnot(None)) & (KnowledgeRelation.last_confirmed_at < cutoff))),
    ).order_by(KnowledgeRelation.updated_at.asc()).limit(min(limit, 200)).all()
    stale_ids = {relation.id for relation in rows}
    return [item for item in graph_audit(db, user_id, limit=200) if item["id"] in stale_ids][:min(limit, 200)]


def graph_audit(db: Session, user_id: Optional[int], node_id: Optional[int] = None, limit: int = 100) -> list[dict]:
    """Devuelve trazabilidad de relaciones propias, incluidas las archivadas."""
    if not user_id or limit <= 0:
        return []
    query = db.query(KnowledgeRelation).filter(KnowledgeRelation.user_id == user_id)
    if node_id is not None:
        query = query.filter(
            (KnowledgeRelation.from_node_id == node_id) | (KnowledgeRelation.to_node_id == node_id),
        )
    rows = query.order_by(KnowledgeRelation.updated_at.desc(), KnowledgeRelation.id.desc()).limit(min(limit, 200)).all()
    return [
        {
            "id": relation.id,
            "from": {"id": relation.from_node.id, "type": relation.from_node.node_type, "name": relation.from_node.name},
            "to": {"id": relation.to_node.id, "type": relation.to_node.node_type, "name": relation.to_node.name},
            "relation": relation.relation_type,
            "status": relation.status,
            "confidence": relation.confidence,
            "weight": relation.weight,
            "source": relation.source,
            "source_ref": relation.source_ref,
            "valid_from": relation.valid_from.isoformat() if relation.valid_from else None,
            "valid_until": relation.valid_until.isoformat() if relation.valid_until else None,
            "last_confirmed_at": relation.last_confirmed_at.isoformat() if relation.last_confirmed_at else None,
            "updated_at": relation.updated_at.isoformat() if relation.updated_at else None,
        }
        for relation in rows
        if relation.from_node is not None and relation.to_node is not None
    ]


def save_graph(db: Session) -> None:
    """Confirma una operación de grafo en una sola transacción."""
    db.commit()


__all__ = [
    "GraphFact", "extract_explicit_facts", "remember_explicit_facts",
    "graph_context", "graph_neighbors", "search_graph_nodes", "graph_audit", "confirm_graph_relation", "set_graph_relation_status", "stale_graph_relations", "upsert_node", "upsert_relation", "save_graph",
]
