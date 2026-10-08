#!/usr/bin/env python3
"""
Prueba del webhook de Telegram y del enrutado de los recordatorios, sin red.

Son las dos piezas donde un error no da un mensaje raro: da una fuga de datos.
Si el webhook se equivoca de identidad, un usuario lee el correo de otro; si el
planificador se equivoca de destino, un recordatorio privado acaba en el chat de
otra persona. Por eso se comprueban aquí, y no solo en el despliegue.

Cómo se prueba sin hablar con Telegram:
  - Se llama directamente a process_telegram_update() con el MISMO JSON que
    Telegram envía al webhook (así se prueba el parseo real de la librería).
  - Se sustituye Bot.send_message y Message.reply_text por funciones que apuntan
    lo que se habría enviado, y Bot.send_chat_action por una que no hace nada
    (el "escribiendo…" sí es una llamada de red de verdad).

No necesita servidor: monta su propia base SQLite temporal.
"""
import asyncio
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)

# La configuración se fija ANTES de importar server.main, que lee el entorno al
# cargarse. La base es un archivo aparte para no tocar la de las otras suites.
BASE_DATOS = os.path.join(RAIZ, "igris_telegram_test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{BASE_DATOS}"
os.environ.setdefault("IGRIS_ACCESS_KEY", "clave-de-pruebas")
os.environ.setdefault("SECRET_KEY", "secreto-de-pruebas-para-firmar")
os.environ["TELEGRAM_TOKEN"] = "123456:tokenDePruebaQueNoSeUsa"
# Estas dos cambian el comportamiento que se quiere probar, así que se limpian:
#   - sin secreto, el webhook no exige cabecera
#   - sin lista de permitidos, nadie entra "por ser del dueño"
os.environ.pop("TELEGRAM_WEBHOOK_SECRET", None)
os.environ.pop("ALLOWED_TELEGRAM_IDS", None)

passed, failed = 0, []


def check(name, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed.append(name)
        print(f"  ❌ {name} {detail}")


# La base se borra ANTES de importar el servidor. Si se borrara después, el motor
# ya tendría el archivo abierto: en Linux borrar un archivo abierto no lo elimina,
# y todas las escrituras fallarían con "attempt to write a readonly database".
for _archivo in (BASE_DATOS, BASE_DATOS + "-journal"):
    if os.path.exists(_archivo):
        os.remove(_archivo)


# ---------------------------------------------------------------- entorno falso
import server.main as m                              # noqa: E402
from telegram import Bot, Message                    # noqa: E402
from core import database, telegram_links            # noqa: E402
from core.database import TelegramLink, User         # noqa: E402
from core.auth import hash_password                   # noqa: E402

enviados: list = []


async def _send_message_falso(self, chat_id=None, text=None, **kw):
    enviados.append({"chat_id": chat_id, "text": text})


async def _reply_falso(self, text=None, **kw):
    enviados.append({"chat_id": self.chat_id, "text": text, "reply": True})
    return None


async def _chat_action_falsa(self, *a, **kw):
    return None


Bot.send_message = _send_message_falso
Bot.send_chat_action = _chat_action_falsa
Message.reply_text = _reply_falso


def update(chat_id, texto, username="tester"):
    """El mismo JSON que Telegram manda al webhook para un mensaje de texto."""
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "date": 1700000000,
            "chat": {"id": chat_id, "type": "private"},
            "from": {
                "id": chat_id, "is_bot": False, "first_name": "Prueba",
                "username": username, "language_code": "es",
            },
            "text": texto,
        },
    }


def enviar(chat_id, texto):
    """Procesa un mensaje y devuelve lo que Igris habría contestado."""
    enviados.clear()
    asyncio.run(m.process_telegram_update(update(chat_id, texto)))
    return list(enviados)


def textos(respuesta):
    return " | ".join((e["text"] or "") for e in respuesta)


# ---------------------------------------------------------------- preparación
database.init_db()

CHAT_BASICO = 700001
CHAT_SIN_PERMISOS = 700002
CHAT_DUENO = 800001

with database.SessionLocal() as db:
    for nombre, correo in (("tgbasico", "tgbasico@z.com"), ("tgsinpermisos", "tgsin@z.com")):
        db.add(User(username=nombre, email=correo, password_hash=hash_password("claveSegura123")))
    db.commit()
    basico = db.query(User).filter(User.username == "tgbasico").first()
    sin_permisos = db.query(User).filter(User.username == "tgsinpermisos").first()
    basico.can_use_notes = True
    basico.can_use_reminders = True
    sin_permisos.can_use_notes = False
    sin_permisos.can_use_reminders = False
    db.commit()
    BASICO_ID, SIN_PERMISOS_ID = basico.id, sin_permisos.id

    # Un código de vinculación como el que pide el usuario desde su página.
    import secrets
    from datetime import datetime, timedelta
    codigo = f"{secrets.randbelow(10 ** 6):06d}"
    link = TelegramLink(user_id=BASICO_ID)
    link.link_code = codigo
    link.code_expires_at = datetime.utcnow() + timedelta(minutes=15)
    db.add(link)
    db.commit()

print("\n=== IGRIS — TELEGRAM Y RECORDATORIOS ===\n")

# ------------------------------------------------- 1. NADIE ENTRA SIN PERMISO
print("1) Un chat desconocido no entra")
r = enviar(CHAT_BASICO, "hola igris")
check("se le dice que no se le reconoce", "No reconozco este chat" in textos(r), f"({textos(r)[:80]})")
check("y se le explica cómo vincularse", "/start" in textos(r))
check("no queda vinculado", telegram_links.resolve_user(CHAT_BASICO) is None)

print("\n2) Un código inventado no vincula")
r = enviar(CHAT_BASICO, "/start 000000")
check("no queda vinculado", telegram_links.resolve_user(CHAT_BASICO) is None)
check("se le explica qué hacer", "Conexiones" in textos(r), f"({textos(r)[:90]})")

# ------------------------------------------------------------- 3. VINCULACIÓN
print("\n3) Vinculación con el código real")
r = enviar(CHAT_BASICO, f"/start {codigo}")
vinculado = telegram_links.resolve_user(CHAT_BASICO)
check("el chat queda vinculado", vinculado is not None)
check("se confirma al usuario", "vinculado" in textos(r), f"({textos(r)[:80]})")
check("queda vinculado al usuario correcto", vinculado is not None and vinculado.id == BASICO_ID,
      f"({getattr(vinculado, 'username', None)})")

print("\n4) El código es de un solo uso")
r = enviar(CHAT_SIN_PERMISOS, f"/start {codigo}")
check("otro chat no puede reutilizarlo",
      telegram_links.resolve_user(CHAT_SIN_PERMISOS) is None)
check("el primero sigue vinculado",
      telegram_links.resolve_user(CHAT_BASICO) is not None)
check("y no se le cambia de dueño",
      telegram_links.resolve_user(CHAT_BASICO).id == BASICO_ID)

# ------------------------------------------- 5. SE ATIENDE COMO ESE USUARIO
print("\n5) Un chat vinculado se atiende como SU usuario, con SUS permisos")

capturado = {}


class SesionFalsa:
    """Sustituye a la sesión real para ver qué identidad le llega."""
    user_id = None
    capabilities = None
    addressing_instruction = ""
    telegram_linked = False
    google_linked = None
    telegram_id = None

    async def say(self, texto):
        capturado.update(
            user_id=self.user_id, caps=self.capabilities,
            telegram_id=self.telegram_id, texto=texto,
        )
        return "respuesta de prueba"


m.sessions.get = lambda clave: SesionFalsa()
r = enviar(CHAT_BASICO, "¿qué hora es?")
check("la sesión lleva el id del usuario vinculado", capturado.get("user_id") == BASICO_ID,
      f"({capturado.get('user_id')} en vez de {BASICO_ID})")
check("la sesión lleva SUS permisos (ni más ni menos)",
      capturado.get("caps") is not None
      and capturado["caps"].features == frozenset({"time", "weather", "notes", "reminders"}),
      f"({sorted(getattr(capturado.get('caps'), 'features', []))})")
check("la sesión sabe a qué chat avisar", capturado.get("telegram_id") == CHAT_BASICO)
check("y el usuario recibe la respuesta", "respuesta de prueba" in textos(r))

# ------------------------------------- 6. UN USUARIO NO ES ADMINISTRADOR
print("\n6) Un usuario vinculado NO puede cambiar la configuración de todos")
for comando in ("/config", "/setprovider openai", "/setfallback openai,local"):
    r = enviar(CHAT_BASICO, comando)
    check(f"'{comando.split()[0]}' se le niega", "administrador" in textos(r),
          f"({textos(r)[:80]})")

print("\n7) El dueño (ALLOWED_TELEGRAM_IDS) conserva sus comandos")
m.ALLOWED_TELEGRAM_IDS.add(CHAT_DUENO)
r = enviar(CHAT_DUENO, "/config")
check("el dueño sí ve la configuración", "Configuración" in textos(r), f"({textos(r)[:90]})")
r = enviar(CHAT_DUENO, "/setprovider")
check("y sigue recibiendo el uso correcto", "Uso:" in textos(r), f"({textos(r)[:80]})")
m.ALLOWED_TELEGRAM_IDS.discard(CHAT_DUENO)

# ------------------------------------------------------- 8. DESVINCULAR CORTA
print("\n8) Desvincular corta el acceso en el acto")
with database.SessionLocal() as db:
    lk = db.query(TelegramLink).filter(TelegramLink.user_id == BASICO_ID).first()
    lk.chat_id = None
    lk.username = None
    db.commit()
check("el chat ya no resuelve a nadie", telegram_links.resolve_user(CHAT_BASICO) is None)
r = enviar(CHAT_BASICO, "hola")
check("vuelve a ser un desconocido", "No reconozco este chat" in textos(r), f"({textos(r)[:80]})")

# ----------------------------------------- 9. ENRUTADO DE LOS RECORDATORIOS
print("\n9) A qué chat va cada recordatorio")
from core.scheduler import _targets_for, build_message, next_due  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402

check("con chat guardado, va a ESE chat",
      _targets_for({"chat_id": 111, "user_id": 5}, [999], {5: 222}) == [111])
check("sin chat guardado, al que tenga vinculado AHORA",
      _targets_for({"chat_id": None, "user_id": 5}, [999], {5: 222}) == [222])
check("un usuario sin Telegram vinculado no recibe nada",
      _targets_for({"chat_id": None, "user_id": 5}, [999], {}) == [])
check("un recordatorio antiguo sin dueño va a los chats de la instalación",
      _targets_for({"chat_id": None, "user_id": None}, [999, 888], {}) == [888, 999])
check("el chat guardado manda sobre el vinculado después",
      _targets_for({"chat_id": 111, "user_id": 5}, [999], {5: 222}) == [111])

print("\n10) El aviso no filtra el texto a quien no debe")
# Un recordatorio de un usuario sin Telegram vinculado se queda pendiente: si se
# enviara a los chats por defecto, su texto privado lo leería el dueño.
with database.SessionLocal() as db:
    from core.database import Reminder
    db.query(Reminder).filter(Reminder.text.like("PRUEBA-%")).delete(synchronize_session=False)
    db.add(Reminder(user_id=SIN_PERMISOS_ID, text="PRUEBA-secreto-de-ana",
                    due_at=datetime.utcnow() - timedelta(minutes=1), status="pendiente",
                    repeat="none", attempts=0))
    db.commit()

from core.scheduler import process_due  # noqa: E402

avisos: list = []


async def _envio_falso(chat_id, texto):
    avisos.append((chat_id, texto))


asyncio.run(process_due(_envio_falso, [CHAT_DUENO]))
check("no se avisa a los chats del dueño", avisos == [], f"({avisos})")
with database.SessionLocal() as db:
    estado = db.query(Reminder).filter(
        Reminder.text == "PRUEBA-secreto-de-ana").first().status
check("el recordatorio sigue pendiente (no se pierde)", estado == "pendiente", f"({estado})")

print("\n11) En cuanto vincula, el aviso sale a SU chat")
with database.SessionLocal() as db:
    link = TelegramLink(user_id=SIN_PERMISOS_ID, chat_id=CHAT_SIN_PERMISOS)
    db.add(link)
    db.commit()
avisos.clear()
asyncio.run(process_due(_envio_falso, [CHAT_DUENO]))
check("el aviso sale por fin", len(avisos) == 1, f"({avisos})")
check("y va SOLO a su chat", all(c == CHAT_SIN_PERMISOS for c, _ in avisos), f"({avisos})")
check("con el texto del recordatorio", avisos and "PRUEBA-secreto-de-ana" in avisos[0][1])
check("el dueño no ve nada", all(c != CHAT_DUENO for c, _ in avisos))

print("\n12) Dos recordatorios de dos usuarios no se cruzan")
with database.SessionLocal() as db:
    # Básico quedó desvinculado en el punto 8; se vuelve a vincular para que sus
    # avisos tengan destino. Sin esto, su recordatorio se quedaría pendiente (que
    # es lo correcto, pero no lo que aquí se quiere medir).
    lk = db.query(TelegramLink).filter(TelegramLink.user_id == BASICO_ID).first()
    lk.chat_id = CHAT_BASICO
    db.query(Reminder).filter(Reminder.text.like("PRUEBA-%")).delete(synchronize_session=False)
    ahora = datetime.utcnow() - timedelta(minutes=1)
    db.add(Reminder(user_id=BASICO_ID, text="PRUEBA-de-basico", due_at=ahora,
                    status="pendiente", repeat="none", attempts=0))
    db.add(Reminder(user_id=SIN_PERMISOS_ID, text="PRUEBA-de-ana", due_at=ahora,
                    status="pendiente", repeat="none", attempts=0))
    db.commit()
avisos.clear()
asyncio.run(process_due(_envio_falso, [CHAT_DUENO]))
check("el aviso de básico va a su chat",
      any(c == CHAT_BASICO and "PRUEBA-de-basico" in t for c, t in avisos), f"({avisos})")
check("y el de ana al de ana",
      any(c == CHAT_SIN_PERMISOS and "PRUEBA-de-ana" in t for c, t in avisos), f"({avisos})")
check("ninguno acaba en los chats del dueño",
      all(c != CHAT_DUENO for c, _ in avisos), f"({avisos})")

print("\n13) Un recordatorio viejo y sin dueño sigue avisando como siempre")
with database.SessionLocal() as db:
    db.query(Reminder).filter(Reminder.text.like("PRUEBA-%")).delete(synchronize_session=False)
    db.add(Reminder(user_id=None, text="PRUEBA-antiguo",
                    due_at=datetime.utcnow() - timedelta(minutes=1), status="pendiente",
                    repeat="none", attempts=0))
    db.commit()
avisos.clear()
asyncio.run(process_due(_envio_falso, [CHAT_DUENO]))
check("va a los chats de la instalación",
      any(c == CHAT_DUENO and "PRUEBA-antiguo" in t for c, t in avisos), f"({avisos})")

# ------------------------------------------------------------------ limpieza
with database.SessionLocal() as db:
    db.query(Reminder).filter(Reminder.text.like("PRUEBA-%")).delete(synchronize_session=False)
    db.query(TelegramLink).delete(synchronize_session=False)
    db.query(User).filter(User.username.in_(["tgbasico", "tgsinpermisos"])).delete(
        synchronize_session=False)
    db.commit()
for archivo in (BASE_DATOS, BASE_DATOS + "-journal"):
    if os.path.exists(archivo):
        os.remove(archivo)

print(f"\n{'='*58}")
print(f"  RESULTADO Telegram: {passed} superadas, {len(failed)} fallidas")
if failed:
    print("\n  Fallidas:")
    for f in failed:
        print(f"    - {f}")
print(f"{'='*58}\n")

sys.exit(1 if failed else 0)
