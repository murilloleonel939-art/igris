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
from core.neural import record_experience


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
    (re.compile(r"\bme llamo\s+(.+?)(?:\s+y\s+(?:trabajo|vivo|prefiero|me gusta)|\s*[,;.]|$)", re.I), "person", "name", "person", "user"),
    (re.compile(r"(?<!no )\b(?:prefiero|me gusta|me encanta)\s+(.+?)(?:\s+y\s+(?:prefiero|me gusta|trabajo|vivo)|\s*[,;.]|$)", re.I), "person", "prefers", "preference", "user"),
    (re.compile(r"\bno me gusta\s+(.+?)(?:\s+y\s+(?:prefiero|me gusta|trabajo|vivo)|\s*[,;.]|$)", re.I), "person", "dislikes", "preference", "user"),
    (re.compile(r"\b(?:trabajo en|estoy trabajando en)\s+(.+?)(?:\s+con\s+[A-ZÁÉÍÓÚÑ]|\s+y\s+(?:prefiero|me gusta|vivo|uso)|\s*[,;.]|\s+usando\b|$)", re.I), "person", "works_on", "project", "user"),
    (re.compile(r"\b(?:trabajo con)\s+([A-ZÁÉÍÓÚÑ][\wáéíóúñü]{1,40})(?:\s+y\b|\s*[,;.]|$)", re.I), "person", "works_with", "person", "user"),
    (re.compile(r"\btrabajo (?:en\s+.+?\s+)?con\s+([A-ZÁÉÍÓÚÑ][\wáéíóúñü]{1,40})", re.I), "person", "works_with", "person", "user"),
    (re.compile(r"\b(?:vivo en|soy de|estoy en)\s+(.+?)(?:\s+y\s+(?:prefiero|me gusta|trabajo)|\s*[,;.]|$)", re.I), "person", "lives_in", "place", "user"),
    (re.compile(r"\b(?:mi objetivo es|mi objetivo:|mi meta es)\s+(.+?)(?:\s*[,;.]|$)", re.I), "person", "has_goal", "goal", "user"),
    (re.compile(r"\b(?:el proyecto|proyecto|la app|la aplicación)\s+(.+?)\s+(?:usa|utiliza|está hecho en|es con)\s+(.+?)(?:\s*[,;.]|$)", re.I), "project", "uses", "technology", "project"),
    (re.compile(r"\b(?:estoy aprendiendo|quiero aprender|aprendiendo)\s+(.+?)(?:\s*[,;.]|$)", re.I), "person", "learning", "skill", "user"),
    (re.compile(r"\b(?:uso|utilizo)\s+([A-Za-z][\w.+#-]{1,30})(?:\s+(?:para|en|como)\b|\s*[,;.]|$)", re.I), "person", "uses", "technology", "user"),
    (re.compile(r"\b(?:mi (?:hermano|hermana|madre|padre|esposa|esposo|hijo|hija|amigo|amiga|jefe|jefa))\s+(?:se llama\s+)?([A-ZÁÉÍÓÚÑ][\wáéíóúñü]{1,40})", re.I), "person", "related_to", "person", "user"),
    (re.compile(r"\b(?:tengo|tenemos)\s+(\d{1,3}\s+(?:años|cabezas|empleados|personas|hijos|hijas|mascotas))\b", re.I), "person", "has_count", "quantity", "user"),
    (re.compile(r"\b(?:nací el|mi cumpleaños es|cumplo años el)\s+(.+?)(?:\s*[,;.]|$)", re.I), "person", "birthday", "date", "user"),
    (re.compile(r"\b(?:trabajo como|soy)\s+(?:un |una |el |la )?([A-Za-zÁÉÍÓÚÑáéíóúñ]{3,40})(?:\s*[,;.]|\s+en\b|$)", re.I), "person", "has_role", "role", "user"),
)

_TOPIC_HINTS = {
    "tecnología": ("código", "programa", "api", "python", "javascript", "base de datos", "servidor", "app", "software", "deploy"),
    "trabajo": ("trabajo", "proyecto", "empresa", "cliente", "jefe", "reunión", "oficina", "equipo"),
    "salud": ("salud", "médico", "ejercicio", "gimnasio", "dieta", "dormir", "enfermo"),
    "finanzas": ("dinero", "pago", "factura", "presupuesto", "inversión", "banco", "precio", "coste"),
    "familia": ("familia", "hijo", "hija", "mamá", "papá", "hermano", "esposa", "pareja"),
    "estudio": ("estudio", "curso", "aprender", "universidad", "examen", "clase"),
    "viaje": ("viaje", "vuelo", "hotel", "vacaciones", "ciudad", "país"),
    "ocio": ("película", "música", "juego", "serie", "libro", "deporte", "fútbol"),
}


def _split_clauses(text: str) -> list[str]:
    """Divide un mensaje en cláusulas independientes sin perder el orden."""
    return [part.strip() for part in re.split(r"(?:[,;]|\s+y\s+(?=\w))", text) if part.strip()]


def _clean_object(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", (value or "").strip(" .,;:"))
    return cleaned[:255]


def extract_explicit_facts(user_text: str) -> list[GraphFact]:
    """Extrae todos los hechos detectables, sin exigir que abran la frase.

    Cada cláusula del mensaje se evalúa por separado, de modo que una frase con
    varios datos produce varios hechos en lugar de quedarse con el primero.
    """
    text = re.sub(r"\s+", " ", (user_text or "")).strip()
    if len(text) < 4:
        return []
    low = text.lower()
    if low.startswith(("olvida que", "borra de tu memoria", "no recuerdes")):
        return []
    # Una corrección ("ya no trabajo en X") no es una afirmación nueva: su
    # trabajo es archivar la relación anterior y no debe reforzarla.
    if re.search(r"\b(?:ya no|dejé de|deje de)\b", low):
        return []
    facts: list[GraphFact] = []
    seen: set[tuple[str, str, str]] = set()
    for clause in _split_clauses(text):
        for pattern, subject_type, relation, object_type, _ in _FACT_PATTERNS:
            match = pattern.search(clause)
            if not match:
                continue
            groups = match.groups()
            if len(groups) == 1:
                subject_name, object_name = "user", _clean_object(groups[0])
            else:
                subject_name, object_name = _clean_object(groups[0]), _clean_object(groups[1])
            if not (2 <= len(object_name) <= 255):
                continue
            key = (subject_name.lower(), relation, object_name.lower())
            if key in seen:
                continue
            seen.add(key)
            facts.append(GraphFact(subject_type, subject_name or "user", relation, object_type, object_name))
    return facts


def extract_topics(user_text: str, limit: int = 3) -> list[str]:
    """Devuelve los temas reconocibles del texto, ordenados por coincidencias."""
    low = (user_text or "").lower()
    scored = [
        (sum(1 for word in words if word in low), topic)
        for topic, words in _TOPIC_HINTS.items()
    ]
    return [topic for score, topic in sorted(scored, reverse=True) if score > 0][:limit]


def _apply_corrections(db: Session, user_id: int, user_text: str) -> bool:
    """Archiva relaciones contradichas por una corrección explícita."""
    text = re.sub(r"\s+", " ", (user_text or "")).strip().rstrip(".!?")
    match = re.search(r"\b(?:ya no|dejé de|deje de)\s+(trabajar en|estar trabajando en|preferir|me gusta|gustar)\s+(.+?)(?:\s*[,;.]|$)", text, re.I)
    if not match:
        return False
    relation_type = "works_on" if "trabaj" in match.group(1).lower() else "prefers"
    target_name = match.group(2).strip().strip(".,;")
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
    # Solo las relaciones de valor único se archivan al cambiar: una persona
    # puede preferir varias cosas o aprender varias a la vez.
    exclusive = {"works_on", "lives_in", "has_goal", "name", "has_role", "birthday"}
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


def _link_conversation(
    db: Session,
    user_id: int,
    text: str,
    *,
    source: str,
    source_ref: Optional[str],
    session_key: Optional[str],
    turn_role: str = "user",
) -> int:
    """Conecta el turno con un nodo de conversación y con sus temas.

    Cada conversación se identifica por ``session_key``; si no se conoce, se usa
    un nodo diario para no perder el hilo. Los temas se enlazan con ``about``.
    """
    topics = extract_topics(text)
    if not topics and not session_key:
        return 0
    conversation_name = (session_key or utcnow().strftime("%Y-%m-%d"))[:255]
    conversation = upsert_node(
        db, user_id, "conversation", conversation_name,
        confidence=80, importance=2, source=source, source_ref=source_ref,
    )
    linked = 0
    for topic in topics:
        topic_node = upsert_node(
            db, user_id, "topic", topic,
            confidence=85, importance=2, source=source, source_ref=source_ref,
        )
        if db.query(KnowledgeRelation).filter(
            KnowledgeRelation.user_id == user_id,
            KnowledgeRelation.from_node_id == conversation.id,
            KnowledgeRelation.to_node_id == topic_node.id,
            KnowledgeRelation.relation_type == "about",
        ).first() is None:
            upsert_relation(db, user_id, conversation, "about", topic_node, confidence=85, source=source, source_ref=source_ref)
            linked += 1
    anchor_type = "assistant" if turn_role == "assistant" else "user"
    anchor = upsert_node(
        db, user_id, "user" if anchor_type == "user" else "assistant", anchor_type,
        confidence=90, importance=3, source=source, source_ref=source_ref,
    )
    relation_type = "answered_in" if turn_role == "assistant" else "participated_in"
    if db.query(KnowledgeRelation).filter(
        KnowledgeRelation.user_id == user_id,
        KnowledgeRelation.from_node_id == anchor.id,
        KnowledgeRelation.to_node_id == conversation.id,
        KnowledgeRelation.relation_type == relation_type,
    ).first() is None:
        upsert_relation(db, user_id, anchor, relation_type, conversation, confidence=85, source=source, source_ref=source_ref)
    return linked


def learn_from_assistant(
    db: Session,
    user_id: Optional[int],
    assistant_text: str,
    *,
    source: str = "chat",
    source_ref: Optional[str] = None,
    session_key: Optional[str] = None,
) -> int:
    """Registra en el grafo de qué habló Igris, sin inventar datos del usuario.

    Solo se extraen temas y la pertenencia a la conversación: el texto del
    asistente nunca crea entidades personales, para no fabricar recuerdos.
    """
    if not user_id:
        return 0
    text = (assistant_text or "").strip()
    if len(text) < 12:
        return 0
    try:
        linked = _link_conversation(
            db, user_id, text,
            source=source, source_ref=source_ref,
            session_key=session_key, turn_role="assistant",
        )
        labels = extract_topics(text)
        if labels:
            record_experience(db, user_id, text, labels, response=text, source=source)
        if linked:
            db.commit()
        return linked
    except Exception:
        db.rollback()
        return 0


def link_memory_fact(
    db: Session,
    user_id: Optional[int],
    content: str,
    *,
    kind: str = "personal",
    source: str = "memory",
    source_ref: Optional[str] = None,
) -> int:
    """Convierte un recuerdo textual en entidades y relaciones del grafo.

    Así ``UserMemory`` deja de ser un cajón aislado: cada frase guardada aporta
    sus hechos y sus temas a la red, sin duplicar la memoria ni descartarla.
    """
    if not user_id:
        return 0
    text = (content or "").strip()
    if len(text) < 4:
        return 0
    try:
        facts = extract_explicit_facts(text)
        for fact in facts:
            subject = upsert_node(db, user_id, fact.subject_type, fact.subject, confidence=85, importance=2, source=source, source_ref=source_ref)
            target = upsert_node(db, user_id, fact.object_type, fact.object, confidence=85, importance=2, source=source, source_ref=source_ref)
            _supersede_conflicting_relations(db, user_id, subject, fact.relation, target)
            relation = upsert_relation(db, user_id, subject, fact.relation, target, confidence=85, source=source, source_ref=source_ref)
            if kind == "operational":
                relation.weight = max(1, min(100, relation.weight))
        topics = extract_topics(text)
        for topic in topics:
            topic_node = upsert_node(db, user_id, "topic", topic, confidence=80, importance=2, source=source, source_ref=source_ref)
            user_node = upsert_node(db, user_id, "user", "user", confidence=90, importance=3, source=source, source_ref=source_ref)
            if db.query(KnowledgeRelation).filter(
                KnowledgeRelation.user_id == user_id,
                KnowledgeRelation.from_node_id == user_node.id,
                KnowledgeRelation.to_node_id == topic_node.id,
                KnowledgeRelation.relation_type == "interested_in",
            ).first() is None:
                upsert_relation(db, user_id, user_node, "interested_in", topic_node, confidence=80, source=source, source_ref=source_ref)
        if facts or topics:
            db.commit()
            schedule_node_embedding_backfill(user_id)
        return len(facts)
    except Exception:
        db.rollback()
        return 0


def remember_explicit_facts(
    db: Session,
    user_id: int,
    user_text: str,
    *,
    source: str = "chat",
    source_ref: Optional[str] = None,
    session_key: Optional[str] = None,
) -> int:
    """Persiste hechos explícitos y correcciones sin tocar UserMemory.

    Además de los datos personales, enlaza el turno con un nodo de conversación
    y con los temas detectados, para que el grafo también recuerde de qué se habló.
    """
    corrected = _apply_corrections(db, user_id, user_text)
    facts = extract_explicit_facts(user_text)
    for fact in facts:
        subject = upsert_node(db, user_id, fact.subject_type, fact.subject, confidence=95, importance=3, source=source, source_ref=source_ref)
        target = upsert_node(db, user_id, fact.object_type, fact.object, confidence=95, importance=3, source=source, source_ref=source_ref)
        _supersede_conflicting_relations(db, user_id, subject, fact.relation, target)
        upsert_relation(db, user_id, subject, fact.relation, target, confidence=95, source=source, source_ref=source_ref)
    topics = 0
    if len((user_text or "").strip()) >= 12:
        topics = _link_conversation(db, user_id, user_text, source=source, source_ref=source_ref, session_key=session_key)
    if facts or corrected or topics:
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


def export_graph(db: Session, user_id: Optional[int]) -> dict:
    """Exporta únicamente el grafo propio, sin ids reutilizables entre cuentas."""
    if not user_id:
        return {"version": 1, "nodes": [], "relations": []}
    nodes = db.query(KnowledgeNode).filter(KnowledgeNode.user_id == user_id).order_by(KnowledgeNode.id.asc()).all()
    node_keys = {(node.node_type, node.name): node for node in nodes}
    relations = db.query(KnowledgeRelation).filter(KnowledgeRelation.user_id == user_id).order_by(KnowledgeRelation.id.asc()).all()
    return {
        "version": 1,
        "nodes": [{
            "type": node.node_type, "name": node.name, "description": node.description,
            "confidence": node.confidence, "importance": node.importance, "source": node.source,
            "source_ref": node.source_ref, "status": node.status,
            "valid_from": node.valid_from.isoformat() if node.valid_from else None,
            "valid_until": node.valid_until.isoformat() if node.valid_until else None,
        } for node in nodes],
        "relations": [{
            "from": {"type": relation.from_node.node_type, "name": relation.from_node.name},
            "to": {"type": relation.to_node.node_type, "name": relation.to_node.name},
            "relation": relation.relation_type, "confidence": relation.confidence, "weight": relation.weight,
            "source": relation.source, "source_ref": relation.source_ref, "status": relation.status,
            "valid_from": relation.valid_from.isoformat() if relation.valid_from else None,
            "valid_until": relation.valid_until.isoformat() if relation.valid_until else None,
            "last_confirmed_at": relation.last_confirmed_at.isoformat() if relation.last_confirmed_at else None,
        } for relation in relations if relation.from_node and relation.to_node and
        (relation.from_node.node_type, relation.from_node.name) in node_keys and
        (relation.to_node.node_type, relation.to_node.name) in node_keys],
    }


def _import_datetime(value, field: str) -> Optional[datetime]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} debe ser una fecha ISO válida")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} debe ser una fecha ISO válida") from exc


def validate_graph_payload(payload: dict) -> dict:
    """Valida estructura, estados y límites antes de escribir en la base de datos."""
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError("Formato de grafo no compatible")
    nodes = payload.get("nodes", [])
    relations = payload.get("relations", [])
    if not isinstance(nodes, list) or not isinstance(relations, list) or len(nodes) > 1000 or len(relations) > 2000:
        raise ValueError("El grafo excede los límites permitidos")
    node_keys = set()
    for item in nodes:
        if not isinstance(item, dict) or not isinstance(item.get("type"), str) or not isinstance(item.get("name"), str):
            raise ValueError("Entidad inválida en el grafo")
        node_key = (item["type"].strip().lower()[:32], item["name"].strip()[:255])
        if not node_key[0] or not node_key[1] or node_key in node_keys:
            raise ValueError("Hay entidades vacías o duplicadas en el grafo")
        node_keys.add(node_key)
        if item.get("status", "active") not in {"active", "archived"}:
            raise ValueError("Estado de entidad inválido")
        _import_datetime(item.get("valid_from"), "valid_from")
        _import_datetime(item.get("valid_until"), "valid_until")
    relation_keys = set()
    for item in relations:
        if not isinstance(item, dict) or not isinstance(item.get("from"), dict) or not isinstance(item.get("to"), dict):
            raise ValueError("Relación inválida en el grafo")
        source = item["from"]
        target = item["to"]
        if not isinstance(source.get("type"), str) or not isinstance(source.get("name"), str) or not isinstance(target.get("type"), str) or not isinstance(target.get("name"), str):
            raise ValueError("Referencia de relación inválida")
        source_key = (source["type"].strip().lower()[:32], source["name"].strip()[:255])
        target_key = (target["type"].strip().lower()[:32], target["name"].strip()[:255])
        relation_key = (source_key, target_key, str(item.get("relation", "related_to")).strip().lower()[:64])
        if source_key not in node_keys or target_key not in node_keys or source_key == target_key:
            raise ValueError("La relación referencia entidades inválidas")
        if relation_key in relation_keys:
            raise ValueError("Hay relaciones duplicadas en el grafo")
        relation_keys.add(relation_key)
        if item.get("status", "active") not in {"active", "archived", "superseded"}:
            raise ValueError("Estado de relación inválido")
        _import_datetime(item.get("valid_from"), "valid_from")
        _import_datetime(item.get("valid_until"), "valid_until")
        _import_datetime(item.get("last_confirmed_at"), "last_confirmed_at")
    return payload


def preview_graph_import(db: Session, user_id: Optional[int], payload: dict) -> dict:
    """Resume cambios potenciales sin modificar la base de datos."""
    if not user_id:
        raise ValueError("Usuario inválido")
    validate_graph_payload(payload)
    raw_nodes = payload.get("nodes", [])
    raw_relations = payload.get("relations", [])
    node_keys = {(item["type"].strip().lower()[:32], item["name"].strip()[:255]) for item in raw_nodes}
    existing_nodes = {
        (node.node_type, node.name)
        for node in db.query(KnowledgeNode).filter(KnowledgeNode.user_id == user_id).all()
    }
    existing_relations = {
        (relation.from_node.node_type, relation.from_node.name,
         relation.to_node.node_type, relation.to_node.name, relation.relation_type)
        for relation in db.query(KnowledgeRelation).filter(KnowledgeRelation.user_id == user_id).all()
        if relation.from_node is not None and relation.to_node is not None
    }
    relation_keys = [
        (item["from"]["type"].strip().lower()[:32], item["from"]["name"].strip()[:255],
         item["to"]["type"].strip().lower()[:32], item["to"]["name"].strip()[:255],
         str(item.get("relation", "related_to")).strip().lower()[:64])
        for item in raw_relations
    ]
    return {
        "nodes": {"total": len(raw_nodes), "new": len(node_keys - existing_nodes), "existing": len(node_keys & existing_nodes)},
        "relations": {
            "total": len(raw_relations),
            "new": sum(key not in existing_relations for key in relation_keys),
            "existing": sum(key in existing_relations for key in relation_keys),
        },
    }


def import_graph(db: Session, user_id: Optional[int], payload: dict) -> dict:
    """Importa un export validado dentro del usuario autenticado, nunca por ids externos."""
    if not user_id:
        raise ValueError("Usuario inválido")
    validate_graph_payload(payload)
    raw_nodes = payload.get("nodes", [])
    raw_relations = payload.get("relations", [])
    try:
        return _import_graph_atomic(db, user_id, raw_nodes, raw_relations)
    except Exception:
        db.rollback()
        raise


def _import_graph_atomic(db: Session, user_id: int, raw_nodes: list, raw_relations: list) -> dict:
    node_map = {}
    for item in raw_nodes:
        if not isinstance(item, dict) or not isinstance(item.get("type"), str) or not isinstance(item.get("name"), str):
            raise ValueError("Entidad inválida en el grafo")
        node = upsert_node(db, user_id, item["type"], item["name"], description=item.get("description"), confidence=item.get("confidence", 50), importance=item.get("importance", 1), source="import", source_ref=item.get("source_ref"), status=item.get("status", "active"), valid_from=_import_datetime(item.get("valid_from"), "valid_from"), valid_until=_import_datetime(item.get("valid_until"), "valid_until"))
        node_map[(node.node_type, node.name)] = node
    imported = 0
    for item in raw_relations:
        if not isinstance(item, dict) or not isinstance(item.get("from"), dict) or not isinstance(item.get("to"), dict):
            raise ValueError("Relación inválida en el grafo")
        source = node_map.get((item["from"].get("type"), item["from"].get("name")))
        target = node_map.get((item["to"].get("type"), item["to"].get("name")))
        if source is None or target is None:
            raise ValueError("La relación referencia una entidad inexistente")
        relation_type = str(item.get("relation", "related_to")).strip().lower()[:64]
        relation = db.query(KnowledgeRelation).filter(
            KnowledgeRelation.user_id == user_id,
            KnowledgeRelation.from_node_id == source.id,
            KnowledgeRelation.to_node_id == target.id,
            KnowledgeRelation.relation_type == relation_type,
        ).first()
        existed = relation is not None
        if relation is None:
            relation = upsert_relation(db, user_id, source, relation_type, target, confidence=item.get("confidence", 50), source="import", source_ref=item.get("source_ref"), valid_from=_import_datetime(item.get("valid_from"), "valid_from"), valid_until=_import_datetime(item.get("valid_until"), "valid_until"))
        else:
            relation.confidence = _bounded(item.get("confidence", relation.confidence), relation.confidence or 50)
            relation.source = "import"
            relation.source_ref = item.get("source_ref") or relation.source_ref
            relation.valid_from = _import_datetime(item.get("valid_from"), "valid_from") or relation.valid_from
            relation.valid_until = _import_datetime(item.get("valid_until"), "valid_until") or relation.valid_until
        if item.get("status") in {"archived", "superseded"}:
            relation.status = item["status"]
        else:
            relation.status = "active"
        relation.weight = max(1, min(100, int(item.get("weight", relation.weight))))
        relation.last_confirmed_at = _import_datetime(item.get("last_confirmed_at"), "last_confirmed_at") or relation.last_confirmed_at
        if existed:
            relation.updated_at = utcnow()
        imported += 1
    db.commit()
    return {"nodes": len(node_map), "relations": imported}


def graph_summary(db: Session, user_id: Optional[int]) -> dict:
    """Resume el estado del grafo propio sin exponer datos de otras cuentas."""
    if not user_id:
        return {
            "nodes": {"total": 0, "active": 0, "archived": 0, "expired": 0, "by_type": {}},
            "relations": {"total": 0, "active": 0, "archived": 0, "superseded": 0, "expired": 0, "by_type": {}},
            "needs_attention": {"stale_relations": 0, "unconfirmed_relations": 0, "isolated_nodes": 0},
        }
    now = utcnow()
    nodes = db.query(KnowledgeNode).filter(KnowledgeNode.user_id == user_id).all()
    relations = db.query(KnowledgeRelation).filter(KnowledgeRelation.user_id == user_id).all()

    nodes_by_type: dict[str, int] = {}
    expired_nodes = 0
    for node in nodes:
        nodes_by_type[node.node_type] = nodes_by_type.get(node.node_type, 0) + 1
        if node.valid_until is not None and node.valid_until < now:
            expired_nodes += 1

    relations_by_type: dict[str, int] = {}
    expired_relations = 0
    unconfirmed = 0
    for relation in relations:
        relations_by_type[relation.relation_type] = relations_by_type.get(relation.relation_type, 0) + 1
        if relation.valid_until is not None and relation.valid_until < now:
            expired_relations += 1
        if relation.status == "active" and relation.last_confirmed_at is None:
            unconfirmed += 1

    linked_node_ids: set[int] = set()
    for relation in relations:
        if relation.status == "active":
            linked_node_ids.add(relation.from_node_id)
            linked_node_ids.add(relation.to_node_id)
    isolated = sum(1 for node in nodes if node.status == "active" and node.id not in linked_node_ids)

    return {
        "nodes": {
            "total": len(nodes),
            "active": sum(1 for node in nodes if node.status == "active"),
            "archived": sum(1 for node in nodes if node.status == "archived"),
            "expired": expired_nodes,
            "by_type": nodes_by_type,
        },
        "relations": {
            "total": len(relations),
            "active": sum(1 for relation in relations if relation.status == "active"),
            "archived": sum(1 for relation in relations if relation.status == "archived"),
            "superseded": sum(1 for relation in relations if relation.status == "superseded"),
            "expired": expired_relations,
            "by_type": relations_by_type,
        },
        "needs_attention": {
            "stale_relations": len(stale_graph_relations(db, user_id)),
            "unconfirmed_relations": unconfirmed,
            "isolated_nodes": isolated,
        },
    }


def save_graph(db: Session) -> None:
    """Confirma una operación de grafo en una sola transacción."""
    db.commit()


__all__ = [
    "GraphFact", "extract_explicit_facts", "extract_topics", "remember_explicit_facts",
    "learn_from_assistant", "link_memory_fact",
    "graph_context", "graph_neighbors", "search_graph_nodes", "graph_audit", "confirm_graph_relation", "set_graph_relation_status", "stale_graph_relations", "export_graph", "validate_graph_payload", "preview_graph_import", "import_graph", "graph_summary", "upsert_node", "upsert_relation", "save_graph",
]
