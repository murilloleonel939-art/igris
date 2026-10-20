"""Operaciones básicas para la memoria relacional de Igris.

Este módulo no sustituye todavía la memoria textual: permite construir el grafo
progresivamente y conservar el origen, la confianza y la vigencia de cada dato.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

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


def save_graph(db: Session) -> None:
    """Confirma una operación de grafo en una sola transacción."""
    db.commit()


__all__ = ["upsert_node", "upsert_relation", "save_graph"]
