"""Operaciones básicas para la memoria relacional de Igris.

Este módulo no sustituye todavía la memoria textual: permite construir el grafo
progresivamente y conservar el origen, la confianza y la vigencia de cada dato.
"""
from __future__ import annotations

from datetime import datetime
import re
from typing import Optional

from dataclasses import dataclass

from sqlalchemy.orm import Session

from core.database import KnowledgeNode, KnowledgeRelation, utcnow


def _bounded(value: int, default: int = 50) -> int:
    return max(0, min(100, int(value if value is not None else default)))


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
    return len(facts)


def graph_context(db: Session, user_id: Optional[int], query: Optional[str] = None, limit: int = 8) -> list[str]:
    """Devuelve conexiones activas, priorizando las relacionadas con el mensaje."""
    if not user_id:
        return []
    rows = db.query(KnowledgeRelation).filter(
        KnowledgeRelation.user_id == user_id,
        KnowledgeRelation.status == "active",
    ).order_by(
        KnowledgeRelation.confidence.desc(),
        KnowledgeRelation.weight.desc(),
        KnowledgeRelation.updated_at.desc(),
    ).all()
    tokens = {token.lower() for token in re.findall(r"[\wáéíóúñü]{3,}", query or "")}
    if tokens:
        rows.sort(key=lambda relation: (
            bool(tokens & {relation.from_node.name.lower(), relation.to_node.name.lower()}),
            relation.confidence,
            relation.weight,
        ), reverse=True)
    output = []
    for relation in rows[:limit]:
        left = relation.from_node
        right = relation.to_node
        if left is None or right is None or left.status != "active" or right.status != "active":
            continue
        output.append(f"{left.name} —{relation.relation_type}→ {right.name}")
    return output


def graph_neighbors(db: Session, user_id: Optional[int], node_id: int, limit: int = 20) -> list[dict]:
    """Devuelve vecinos activos del nodo, siempre dentro del usuario autenticado."""
    if not user_id or not node_id:
        return []
    node = db.query(KnowledgeNode).filter(
        KnowledgeNode.id == node_id,
        KnowledgeNode.user_id == user_id,
        KnowledgeNode.status == "active",
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


def save_graph(db: Session) -> None:
    """Confirma una operación de grafo en una sola transacción."""
    db.commit()


__all__ = [
    "GraphFact", "extract_explicit_facts", "remember_explicit_facts",
    "graph_context", "graph_neighbors", "upsert_node", "upsert_relation", "save_graph",
]
