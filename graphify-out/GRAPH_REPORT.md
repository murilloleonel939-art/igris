# Graph Report - igrisfase3  (2026-10-23)

## Corpus Check
- 128 files · ~190,652 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 318 file(s) not represented in the graph (top: (none) 295, .exe 6, .xml 4)

## Summary
- 2345 nodes · 4982 edges · 141 communities (104 shown, 37 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 383 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `51d0b956`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- UserChat.vue
- device_routes.py
- knowledge_graph.py
- asyncio
- TvAgentService
- test_telegram.py
- User
- httpx
- App.vue
- tuya.py
- voice.py
- user_routes.py
- ⚔️ IGRIS - Asistente de IA con Avatar, Voz, Chat Web y Telegram
- AdminUsers.vue
- main.py
- 🚀 IGRIS - Deployment Summary (October 4, 2024)
- errorMessage
- os
- WhatsAppClient
- Plan de Arreglo IGRIS — Escalado para 100+ usuarios
- GoogleAccount
- BaseModel
- 🚀 IGRIS Coolify Deployment - Step by Step
- e2e_users.py
- memory.py
- gmail.py
- database.py
- profile_routes.py
- nsis
- Dashboard.vue
- .say_stream
- pwa.js
- Configuration.vue
- auth.py
- 🧰 Capacidades de Igris (herramientas)
- auth_routes.py
- stt.py
- Profile
- typing
- relay.py
- 🚀 IGRIS - Deploy en Coolify (Frontend + Backend)
- LocalAgentHub
- brain.py
- 🎯 COOLIFY - CONFIGURACIÓN FINAL (FUNCIONA)
- 📊 IGRIS - Resumen del Proyecto v2.0.0
- neural.py
- SettingsManager
- AgentConnection
- google_client.py
- agent.py
- Session
- push-to-github.js
- vue
- TelegramLink
- documents.py
- client_voice.py
- process_telegram_update
- desktop/package.json
- web/package.json
- server.js
- TvAccessibilityService
- login
- SessionStore
- settings_manager.py
- spotify.py
- 🚀 IGRIS Frontend - Deployment Checklist
- generate_icons.py
- run_tests.sh
- 🔮 IGRIS Web Platform - Setup Completo
- capabilities.py
- .save
- GlobalSetting
- Archivos de `core/tools/`
- IGRIS_PLAN.md
- get_settings
- verify_2fa
- _system_message
- UserMemory
- IGRIS Chat — ventana de escritorio para Windows
- 🚀 Características
- Brain
- 📱 Integración WhatsApp (Meta Cloud API)
- IGRIS TV Agent
- on_startup
- default.json
- dependencies
- devDependencies
- scripts
- 🎨 Instalación Frontend (Vue 3)
- 🔐 Flujo de Autenticación
- 🛑 Troubleshooting
- update_conversation_summary
- main.rs
- ✅ Completado (Octubre 4, 2024)
- ⚠️ Troubleshooting
- ⚙️ Variables de entorno (Coolify)
- verify_deployment.sh
- 1. Obtener credenciales en Meta
- 🚀 Instalación Backend (FastAPI)
- 🐛 Troubleshooting
- Reminder
- re
- 🐳 Deploy en Coolify (EC2)
- 📊 Endpoints API
- Agente local de IGRIS para Windows
- get_me
- AGENTS.md
- verify_token
- scheduler.py
- push_to_github.sh script
- call_igris_chat
- TUYA_SETUP.md
- verify_and_fix.sh
- sw.js
- igris-chat
- process_due
- ▶️ Despliegue
- test_postgres.py
- 🔐 Las dos superficies de acceso
- get
- SpotifyAccount
- _complete_with_tools
- add_whatsapp_column.py
- get_weather
- Voz
- 2fdb3b6849710270/package.json
- _configured_whatsapp_destination

## God Nodes (most connected - your core abstractions)
1. `Session` - 113 edges
2. `User` - 94 edges
3. `errorMessage()` - 58 edges
4. `get_settings()` - 33 edges
5. `🧰 Capacidades de Igris (herramientas)` - 32 edges
6. `TelegramLink` - 26 edges
7. `Archivos de `core/tools/`` - 26 edges
8. `TvAgentService` - 24 edges
9. `utcnow()` - 24 edges
10. `run_local_action()` - 23 edges

## Surprising Connections (you probably didn't know these)
- `3.2 — LLM client único (singleton)` --references--> `_build_client()`  [INFERRED]
  PLAN_ARREGLO_IGRIS.md → core/brain.py
- `Configuración de IA` --references--> `_complete_with_anthropic()`  [INFERRED]
  README.md → core/brain.py
- `F5 — Verificación de voz por niveles` --references--> `BrainSession`  [INFERRED]
  IGRIS_PLAN.md → core/brain.py
- `Memoria estructurada y estado mental` --references--> `link_memory_fact()`  [INFERRED]
  README.md → core/knowledge_graph.py
- `Funciones por usuario (permisos)` --references--> `run_tool()`  [INFERRED]
  README.md → core/tools/__init__.py

## Import Cycles
- 4-file cycle: `core/__init__.py -> core/brain.py -> core/tools/__init__.py -> core/tools/reminders.py -> core/__init__.py`
- 4-file cycle: `core/__init__.py -> core/brain.py -> core/tools/__init__.py -> core/tools/documents_tool.py -> core/__init__.py`
- 4-file cycle: `core/__init__.py -> core/brain.py -> core/tools/__init__.py -> core/tools/notes.py -> core/__init__.py`
- 4-file cycle: `core/__init__.py -> core/brain.py -> core/tools/__init__.py -> core/tools/spotify.py -> core/__init__.py`

## Communities (141 total, 37 thin omitted)

### Community 0 - "UserChat.vue"
Cohesion: 0.05
Nodes (60): setIgrisState(), cancelMemory(), cancelNewMemory(), chatBox, chatInput, chatMessages, confirmRelation(), conn (+52 more)

### Community 1 - "device_routes.py"
Cohesion: 0.05
Nodes (34): AgentToken, AgentTokenCreate, AgentTokenLink, create_agent_token(), delete_agent_token(), device_program_access(), device_programs(), device_status() (+26 more)

### Community 2 - "knowledge_graph.py"
Cohesion: 0.11
Nodes (19): utcnow(), _apply_corrections(), _bounded(), _clean_object(), _currently_valid(), extract_explicit_facts(), extract_topics(), GraphFact (+11 more)

### Community 3 - "asyncio"
Cohesion: 0.07
Nodes (27): Note, _asked_to_delete(), check_delete(), format_date_local(), format_local(), local_to_utc(), normalize(), register_delete() (+19 more)

### Community 4 - "TvAgentService"
Cohesion: 0.06
Nodes (5): MainActivity, SecurePrefs, LocalBinder, TvAgentService, WebSocketListener

### Community 6 - "User"
Cohesion: 0.09
Nodes (18): authenticate_user(), create_user(), get_user_by_username(), hash_password(), User, model_status(), admin_neural_status(), admin_train_neural() (+10 more)

### Community 7 - "httpx"
Cohesion: 0.10
Nodes (25): confirm_event(), confirm_reschedule(), delete_event(), _fmt(), is_affirmative(), _normalize(), propose_event(), propose_reschedule() (+17 more)

### Community 8 - "App.vue"
Cohesion: 0.06
Nodes (46): axios, pinia, vue-router, api, clearKey(), getKey(), setKey(), ADMIN_ROUTES (+38 more)

### Community 9 - "tuya.py"
Cohesion: 0.09
Nodes (31): _allowed_device(), AmbiguousTuyaDeviceError, _call(), _coerce_value(), _config(), _configured_device_ids(), control_tuya_device(), _device_functions() (+23 more)

### Community 10 - "voice.py"
Cohesion: 0.15
Nodes (11): decrypt(), encrypt(), _fernet(), average_embedding(), deserialize(), embedding(), _get_encoder(), serialize() (+3 more)

### Community 11 - "user_routes.py"
Cohesion: 0.07
Nodes (31): verify_password(), TvBoxPairingCode, TvBoxToken, import_graph(), preview_graph_import(), validate_graph_payload(), bind_sessions(), _clear_fails() (+23 more)

### Community 12 - "⚔️ IGRIS - Asistente de IA con Avatar, Voz, Chat Web y Telegram"
Cohesion: 0.17
Nodes (11): Cambiar el video del avatar, 🙏 Créditos, Cómo funciona el avatar, 🔗 Enlaces útiles, 🧩 Estructura del proyecto, ⚔️ IGRIS - Asistente de IA con Avatar, Voz, Chat Web y Telegram, 📝 Notas importantes, PostgreSQL (+3 more)

### Community 13 - "AdminUsers.vue"
Cohesion: 0.08
Nodes (33): activeTab, adminUnlinkTelegram(), cancelAdminMemory(), createAdminMemory(), createUser(), defaultFeatures(), deleteAdminMemory(), features (+25 more)

### Community 14 - "main.py"
Cohesion: 0.10
Nodes (9): add_csp_header(), ChatRequest, _client_ip(), _ensure_bootstrap_admin(), http_chat(), register_admin_voice(), telegram_webhook(), tts_endpoint() (+1 more)

### Community 15 - "🚀 IGRIS - Deployment Summary (October 4, 2024)"
Cohesion: 0.05
Nodes (41): 1. Push a GitHub, 2. Crear App en Coolify, 3. Configurar Reverse Proxy, 4. Deploy, 5. Verificar Funcionamiento, Antes (Oct 3), Archivo server.js, Archivos Existentes (Backend) (+33 more)

### Community 16 - "errorMessage"
Cohesion: 0.06
Nodes (50): errorMessage(), agentTokens, allowedPrograms, createToken(), deleteToken(), error, fixedPrograms, linking (+42 more)

### Community 17 - "os"
Cohesion: 0.13
Nodes (10): _clean_chain(), get_active_provider(), get_active_provider_config(), get_api_base(), get_api_key(), get_default_config(), get_fallback_chain(), load_settings() (+2 more)

### Community 18 - "WhatsAppClient"
Cohesion: 0.09
Nodes (11): _configured_destination(), send_whatsapp_message(), send_test_message(), WhatsAppAPIError, WhatsAppClient, WhatsAppConfigurationError, Comprobar que funciona, Destinatario (+3 more)

### Community 19 - "Plan de Arreglo IGRIS — Escalado para 100+ usuarios"
Cohesion: 0.08
Nodes (24): 2.1 — Reestructurar WebSocket para no retener conexión, 2.2 — Aumentar pool BD dramáticamente, 2.3 — Redis para sesiones (persistencia + escalabilidad), 3.1 — Envolver queries síncronas en `to_thread()`, 3.2 — LLM client único (singleton), 4.1 — Uvicorn con N workers, 4.2 — HEALTHCHECK, 5.1 — Logging estructurado (+16 more)

### Community 20 - "GoogleAccount"
Cohesion: 0.09
Nodes (18): admin_capabilities(), capabilities_from_user(), GoogleAccount, oauth_configured(), redirect_uri(), scopes_for(), _bind_identity(), google_callback() (+10 more)

### Community 21 - "BaseModel"
Cohesion: 0.16
Nodes (6): GraphRelationConfirmIn, GraphRelationStatusIn, MemoryCreateIn, UserCreateIn, UserUpdateIn, _validate_features()

### Community 22 - "🚀 IGRIS Coolify Deployment - Step by Step"
Cohesion: 0.06
Nodes (34): 3.1 - New Application, 3.2 - Configuración Básica, 3.3 - Build Settings, 3.4 - Environment Variables, 3.5 - Recursos (Opcional), 3.6 - Health Check (Opcional), 5.1 - Acceso al Frontend, 5.2 - Verificar Conexión al Backend (+26 more)

### Community 23 - "e2e_users.py"
Cohesion: 0.09
Nodes (9): denial_message(), reset_agent_user(), set_agent_user(), run_tool(), _intentos(), preflight(), req(), _Sesion (+1 more)

### Community 24 - "memory.py"
Cohesion: 0.10
Nodes (17): MemoryLink, _backfill_node_embeddings(), _cosine_similarity(), _decode_embedding(), _embedding_for(), relevance(), run(), _backfill_embeddings() (+9 more)

### Community 25 - "gmail.py"
Cohesion: 0.14
Nodes (13): _build_raw_message(), _clean(), _decode(), _find_part(), _header(), _html_to_text(), list_emails(), propose_email() (+5 more)

### Community 26 - "database.py"
Cohesion: 0.11
Nodes (8): _build_engine(), _column_exists(), _ensure_postgres_database_exists(), get_db(), init_db(), _owner_user_id(), _run_migrations(), _table_exists()

### Community 27 - "profile_routes.py"
Cohesion: 0.12
Nodes (12): AIConfig, get_current_user(), activate_user(), create_profile(), get_ai_config(), get_dashboard(), get_or_create_ai_config(), get_profile() (+4 more)

### Community 28 - "nsis"
Cohesion: 0.07
Nodes (29): app, security, windows, withGlobalTauri, build, devUrl, frontendDist, bundle (+21 more)

### Community 29 - "Dashboard.vue"
Cohesion: 0.10
Nodes (26): chatBox, chatInput, chatMessages, FATAL, handsFree, isBusy, isListening, isPlayingTTS (+18 more)

### Community 30 - ".say_stream"
Cohesion: 0.11
Nodes (12): BrainSession, _delta(), _build_client(), _close_client(), _complete_with_anthropic(), _mark_provider_failed(), _mark_provider_ok(), _provider_available() (+4 more)

### Community 31 - "pwa.js"
Cohesion: 0.15
Nodes (14): 📲 Instalable como aplicación (PWA), isIos, isStandalone, visible, canInstall, deferredPrompt, detectStandalone(), initPwa() (+6 more)

### Community 32 - "Configuration.vue"
Cohesion: 0.07
Nodes (18): activeTab, aiConfig, availableProviders, computeTypes, editConfig, error, inactiveProviders, loading (+10 more)

### Community 33 - "auth.py"
Cohesion: 0.12
Nodes (11): disable_2fa_for_user(), enable_2fa_for_user(), generate_2fa_secret(), generate_backup_codes(), get_2fa_qr_code(), get_user_by_id(), setup_2fa_for_user(), verify_2fa_code() (+3 more)

### Community 34 - "🧰 Capacidades de Igris (herramientas)"
Cohesion: 0.19
Nodes (22): run_local_action(), capture_screen(), click_screen(), focus_window(), launch_program(), list_windows(), media_control(), navigate_edge() (+14 more)

### Community 35 - "auth_routes.py"
Cohesion: 0.16
Nodes (20): AIConfigResponse, Config, AIConfigUpdate, DashboardResponse, Disable2FARequest, ErrorResponse, ProfileCreate, ProfileResponse (+12 more)

### Community 36 - "stt.py"
Cohesion: 0.13
Nodes (10): _language(), _load_faster_whisper_model(), _load_whisper_model(), _local_engine(), _settings(), _to_bytes(), transcribe(), _transcribe_local() (+2 more)

### Community 37 - "Profile"
Cohesion: 0.06
Nodes (23): Profile, learn_from_assistant(), linked_memories_block(), load_memories(), neural_memory_context(), remember_from_text(), _admin_user_from_bearer(), admin_voice_chat() (+15 more)

### Community 38 - "typing"
Cohesion: 0.07
Nodes (19): call_homeassistant_service(), control_homeassistant_device_for_session(), get_homeassistant_device_state(), get_homeassistant_device_state_for_session(), list_homeassistant_devices(), list_homeassistant_devices_for_session(), turn_off_device(), turn_on_device() (+11 more)

### Community 39 - "relay.py"
Cohesion: 0.23
Nodes (12): authorized_handler(), wrapper(), authorized_only(), config_cmd(), get_igris_ai_config(), help_cmd(), main(), relay_message() (+4 more)

### Community 40 - "🚀 IGRIS - Deploy en Coolify (Frontend + Backend)"
Cohesion: 0.10
Nodes (20): 📝 Actualizaciones, Backend ✅, 🔧 Cambios Realizados, 📦 Checklist Pre-Deploy, 🏃 Desarrollo Local (localhost), 💡 Desarrollo Local vs Producción, 📋 Estado Actual (Oct 2024), 📁 Estructura de Deploy (+12 more)

### Community 42 - "brain.py"
Cohesion: 0.13
Nodes (7): _anthropic_payload(), _close_stream(), _stream_chat(), _StreamFunction, _StreamToolCall, supports_vision(), _tool_content_for_anthropic()

### Community 43 - "🎯 COOLIFY - CONFIGURACIÓN FINAL (FUNCIONA)"
Cohesion: 0.10
Nodes (19): 1️⃣ Abre la App Frontend en Coolify, 2️⃣ Ve a "Build" o "Build Pipeline", 3️⃣ Configura estos campos:, 4️⃣ Runtime / Networking, 5️⃣ Environment Variables, 6️⃣ Deploy, 7️⃣ Espera, 📋 CHECKLIST ANTES DE HACER CLICK EN DEPLOY (+11 more)

### Community 44 - "📊 IGRIS - Resumen del Proyecto v2.0.0"
Cohesion: 0.10
Nodes (19): 📁 Archivos Clave, 🏗️ Arquitectura Final, Backend FastAPI + Autenticación, ✅ COMPLETADO EN ESTA SESIÓN, Documentación, En Coolify, 📊 Estadísticas, Fase 3: Raspberry Pi Sync (+11 more)

### Community 45 - "neural.py"
Cohesion: 0.22
Nodes (11): NeuralExperience, NeuralModelState, _features(), _load_model(), _new_model(), predict_context(), record_experience(), _serialize() (+3 more)

### Community 48 - "google_client.py"
Cohesion: 0.20
Nodes (7): client_config(), env_credentials(), _has_stored_account(), _is_admin(), mark_account_error(), resolve_credentials(), stored_credentials()

### Community 49 - "agent.py"
Cohesion: 0.12
Nodes (19): _BITMAPINFO, _BITMAPINFOHEADER, _capture_screen_png(), configure_token(), save(), enumerate_programs(), enumerate_windows(), callback() (+11 more)

### Community 50 - "Session"
Cohesion: 0.11
Nodes (18): KnowledgeNode, KnowledgeRelation, Session, confirm_graph_relation(), export_graph(), graph_audit(), graph_context(), graph_neighbors() (+10 more)

### Community 51 - "push-to-github.js"
Cohesion: 0.21
Nodes (11): createCommit(), createTree(), FILES_TO_UPLOAD, fs, getLastCommit(), https, httpsRequest(), main() (+3 more)

### Community 52 - "vue"
Cohesion: 0.12
Nodes (15): vue, box, cur, failed, LABELS, PROFILE, props, video (+7 more)

### Community 53 - "TelegramLink"
Cohesion: 0.08
Nodes (15): TelegramLink, chat_for_user(), is_linked(), link_chat(), resolve_user(), unlink_chat(), forget_token(), admin_delete_user_memory() (+7 more)

### Community 54 - "documents.py"
Cohesion: 0.22
Nodes (6): _clean(), make_filename(), normalize_sections(), section_count(), _slug(), create_document()

### Community 55 - "client_voice.py"
Cohesion: 0.15
Nodes (8): main(), play_mp3(), speak(), main(), main(), play_mp3(), record(), speak()

### Community 56 - "process_telegram_update"
Cohesion: 0.17
Nodes (6): get_available_providers(), _get_igris_ai_config(), process_telegram_update(), _set_igris_ai_config(), status(), _transcribe_telegram_file()

### Community 57 - "desktop/package.json"
Cohesion: 0.17
Nodes (11): description, devDependencies, @tauri-apps/cli, name, private, scripts, build, dev (+3 more)

### Community 58 - "web/package.json"
Cohesion: 0.18
Nodes (10): autoprefixer, express, postcss, tailwindcss, vite, @vitejs/plugin-vue, description, name (+2 more)

### Community 59 - "server.js"
Cohesion: 0.20
Nodes (6): app, __dirname, __filename, isUserPath(), renderIndex(), sendIndex()

### Community 61 - "login"
Cohesion: 0.29
Nodes (3): create_access_token(), create_refresh_token(), login()

### Community 63 - "settings_manager.py"
Cohesion: 0.16
Nodes (4): _get_tts_config(), _load_piper(), reload_config(), synthesize()

### Community 64 - "spotify.py"
Cohesion: 0.18
Nodes (16): add_tracks_to_spotify_playlist(), authorization_url(), client_config(), create_spotify_playlist(), get_access_token(), list_spotify_playlists(), oauth_configured(), redirect_uri() (+8 more)

### Community 65 - "🚀 IGRIS Frontend - Deployment Checklist"
Cohesion: 0.18
Nodes (10): 1. Preparar Repositorio, 2. En Coolify Panel, 3. Configurar Dominio, 4. Deploy & Test, 🔧 Archivos Actualizados, 📊 Estructura de Deployment, 🚀 IGRIS Frontend - Deployment Checklist, 🎯 Próximos Pasos para Coolify (+2 more)

### Community 66 - "generate_icons.py"
Cohesion: 0.27
Nodes (4): load_square_source(), main(), make_icon(), make_maskable()

### Community 67 - "run_tests.sh"
Cohesion: 0.53
Nodes (10): arrancar_backend(), limpiar_base(), ocupado(), parar_backends(), resumir(), run_tests.sh script, suite_frontend(), suite_postgres() (+2 more)

### Community 68 - "🔮 IGRIS Web Platform - Setup Completo"
Cohesion: 0.18
Nodes (10): 🧠 Configuración de Proveedores IA, 📚 Estructura del Proyecto, 🔑 Google Authenticator Setup, 🔮 IGRIS Web Platform - Setup Completo, 👥 Perfiles de Usuarios Autorizados, 🔄 Próximos Pasos, 📋 Requisitos, 📱 Sincronización Raspberry Pi (+2 more)

### Community 69 - "capabilities.py"
Cohesion: 0.31
Nodes (3): Capabilities, Feature, tools_for()

### Community 72 - "Archivos de `core/tools/`"
Cohesion: 0.23
Nodes (6): list_events(), _parse_dt(), _format(), get_time(), now_context(), Archivos de `core/tools/`

### Community 73 - "IGRIS_PLAN.md"
Cohesion: 0.05
Nodes (41): A1 — Confirmar la causa, A2 — Lock en `_get_encoder()` (`core/voice.py`), A3 — Locks en las demás cargas diferidas, A4 — Executor acotado, B1 — `/health/deep`, B2 — `/api/stt-stats`, B3 — HEALTHCHECK, BLOQUE A — Estabilizar la caída (+33 more)

### Community 74 - "get_settings"
Cohesion: 0.15
Nodes (13): update_active_provider(), get_settings(), AIConfigResponse, AIConfigUpdate, get_ai_config(), get_stt_config(), STTConfigResponse, STTConfigUpdate (+5 more)

### Community 75 - "verify_2fa"
Cohesion: 0.20
Nodes (5): disable_2fa(), logout(), register(), setup_2fa(), verify_2fa()

### Community 76 - "_system_message"
Cohesion: 0.25
Nodes (4): _capabilities_of(), _facts_block(), _system_message(), _tools_for_anthropic()

### Community 77 - "UserMemory"
Cohesion: 0.17
Nodes (8): UserMemory, admin_create_user_memory(), admin_update_user_memory(), create_user_memory(), list_user_memories(), _memory_json(), MemoryUpdateIn, update_user_memory()

### Community 78 - "IGRIS Chat — ventana de escritorio para Windows"
Cohesion: 0.25
Nodes (7): Compilación, Cómo se presenta al usuario, Dispositivos del equipo, Estructura, IGRIS Chat — ventana de escritorio para Windows, Instalación y desinstalación, Qué carga

### Community 79 - "🚀 Características"
Cohesion: 0.25
Nodes (8): API del backend, Bot de Telegram, 🚀 Características, Configuración de IA, Interfaz web (estilo Jarvis), Memoria de conversación, Requisitos y límites del navegador, Voz

### Community 81 - "📱 Integración WhatsApp (Meta Cloud API)"
Cohesion: 0.29
Nodes (7): 2. Configurar en Coolify (Producción), 3. Guardar el destinatario en Conexiones, 4. Probar en IGRIS, 5. Verificar que llegó el mensaje, 📱 Integración WhatsApp (Meta Cloud API), Notas importantes, Prerequisitos

### Community 82 - "IGRIS TV Agent"
Cohesion: 0.33
Nodes (5): Acciones admitidas, Compilación, Conexión, Emparejamiento, IGRIS TV Agent

### Community 83 - "on_startup"
Cohesion: 0.15
Nodes (10): 1.1 — Red de seguridad: cambiar a Deepgram (5 min, reversible), 1.2 — Caché persistente de modelos STT, 1.3 — Warmup STT en startup (agnóstico al motor), 1.4 — Cola de STT con workers paralelos configurable (CRÍTICO para 100+ usuarios), 1.6 — Lock por motor para evitar carga duplicada, FASE 1 — Quitar el cuelgue del STT (inmediato), on_shutdown(), on_startup() (+2 more)

### Community 84 - "default.json"
Cohesion: 0.33
Nodes (5): description, identifier, permissions, $schema, windows

### Community 85 - "dependencies"
Cohesion: 0.33
Nodes (6): dependencies, axios, express, pinia, vue, vue-router

### Community 86 - "devDependencies"
Cohesion: 0.33
Nodes (6): devDependencies, autoprefixer, postcss, tailwindcss, vite, @vitejs/plugin-vue

### Community 87 - "scripts"
Cohesion: 0.33
Nodes (6): scripts, build, dev, preview, prod, start

### Community 88 - "🎨 Instalación Frontend (Vue 3)"
Cohesion: 0.33
Nodes (6): 1. Navegar al directorio web, 2. Instalar dependencias, 3. Configurar .env, 4. Ejecutar en desarrollo, 5. Build para producción, 🎨 Instalación Frontend (Vue 3)

### Community 89 - "🔐 Flujo de Autenticación"
Cohesion: 0.33
Nodes (6): 1. Registro de Usuario, 2. Login, 3. Setup Google Authenticator, 4. Verificar 2FA, 5. Login con 2FA Habilitado, 🔐 Flujo de Autenticación

### Community 90 - "🛑 Troubleshooting"
Cohesion: 0.40
Nodes (5): Error: "Cannot find module 'express'", Error: "Cannot GET /", Error: CORS en Login, Error: Variable VITE_API_URL no definida, 🛑 Troubleshooting

### Community 91 - "update_conversation_summary"
Cohesion: 0.40
Nodes (3): _clean(), memories_block(), update_conversation_summary()

### Community 93 - "✅ Completado (Octubre 4, 2024)"
Cohesion: 0.40
Nodes (5): 📦 Build, ✅ Completado (Octubre 4, 2024), 🖥️ Configuración de Servidor, 📋 Documentación, 🔒 Seguridad & CORS

### Community 94 - "⚠️ Troubleshooting"
Cohesion: 0.40
Nodes (5): Error: 404 en rutas dinámicas, Error: API_URL undefined, Error: "Cannot find module 'express'", Error: CORS preflight fails, ⚠️ Troubleshooting

### Community 95 - "⚙️ Variables de entorno (Coolify)"
Cohesion: 0.17
Nodes (12): Acceso, Base de datos, Ejemplo mínimo, Ejemplo: `openai` y `anthropic` a través de pateway, Google (correo y calendario), Google (Gmail y Calendar), IA, Otras (+4 more)

### Community 96 - "verify_deployment.sh"
Cohesion: 0.70
Nodes (4): check_mark(), error_mark(), verify_deployment.sh script, warning_mark()

### Community 97 - "1. Obtener credenciales en Meta"
Cohesion: 0.40
Nodes (5): 1.1 Ir a Meta Business Suite, 1.2 Obtener `PHONE_NUMBER_ID`, 1.3 Obtener `BUSINESS_ACCOUNT_ID`, 1.4 Generar `WHATSAPP_TOKEN`, 1. Obtener credenciales en Meta

### Community 98 - "🚀 Instalación Backend (FastAPI)"
Cohesion: 0.40
Nodes (5): 1. Instalar dependencias, 2. Variables de entorno (.env), 3. Inicializar Base de Datos, 4. Ejecutar servidor, 🚀 Instalación Backend (FastAPI)

### Community 99 - "🐛 Troubleshooting"
Cohesion: 0.40
Nodes (5): Error: "Database connection failed", Error: "Form data requires python-multipart", Error: "Secret key not found", Frontend no conecta a backend, 🐛 Troubleshooting

### Community 100 - "Reminder"
Cohesion: 0.20
Nodes (6): Reminder, _confirm(), _release(), _save(), enviar(), update()

### Community 101 - "re"
Cohesion: 0.29
Nodes (4): _clean(), _parse_results(), _result_url(), search_web()

### Community 102 - "🐳 Deploy en Coolify (EC2)"
Cohesion: 0.50
Nodes (4): 1. Dockerfile ya incluido, 2. En Coolify:, 3. Base de Datos en Coolify:, 🐳 Deploy en Coolify (EC2)

### Community 103 - "📊 Endpoints API"
Cohesion: 0.50
Nodes (4): Autenticación, 📊 Endpoints API, Panel de Control, Sistema (Node/RPi)

### Community 104 - "Agente local de IGRIS para Windows"
Cohesion: 0.50
Nodes (3): Agente local de IGRIS para Windows, Instalación desde el ejecutable, Instalación manual

### Community 109 - "scheduler.py"
Cohesion: 0.33
Nodes (4): _add_months(), build_message(), _claim_due(), next_due()

### Community 129 - "process_due"
Cohesion: 0.27
Nodes (4): _deliver(), _linked_chats(), process_due(), run_reminder_loop()

### Community 130 - "▶️ Despliegue"
Cohesion: 0.20
Nodes (10): Agente Android TV Box, Agente local de Windows, Crear archivos en el PC (`create_document`), Cómo probar cada función de Igris, ▶️ Despliegue, Instalación manual, Instalación recomendada, PyTorch solo CPU (+2 more)

### Community 132 - "🔐 Las dos superficies de acceso"
Cohesion: 0.25
Nodes (8): Funciones por usuario (permisos), 🔐 Las dos superficies de acceso, Memoria estructurada y estado mental, Panel de administración de usuarios (`/panel/usuarios`), Pantalla de Conexiones (`/conexiones`), Red neuronal propia y autoaprendizaje, WhatsApp Cloud API (administrador), Área de usuarios (`/u`)

### Community 133 - "get"
Cohesion: 0.25
Nodes (4): auth_check(), get_whatsapp_config(), health(), root()

### Community 134 - "SpotifyAccount"
Cohesion: 0.33
Nodes (5): SpotifyAccount, forget_token(), _consume_spotify_oauth_state(), spotify_callback(), spotify_disconnect()

### Community 135 - "_complete_with_tools"
Cohesion: 0.33
Nodes (3): _complete_with_tools(), max_tokens_for(), _tool_content_for_openai()

### Community 138 - "Voz"
Cohesion: 0.50
Nodes (4): Configuración recomendada en Coolify, Estabilidad de voz y fallback entre proveedores, Verificar la biometría con NVIDIA NeMo/TitaNet, Voz

### Community 139 - "2fdb3b6849710270/package.json"
Cohesion: 0.50
Nodes (3): claude-mem, dependencies, claude-mem

## Knowledge Gaps
- **6 isolated node(s):** `claude-mem`, `@tauri-apps/cli`, `igris-chat`, `autoprefixer`, `postcss` (+1 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1121 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **37 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `⚔️ IGRIS - Asistente de IA con Avatar, Voz, Chat Web y Telegram` connect `⚔️ IGRIS - Asistente de IA con Avatar, Voz, Chat Web y Telegram` to `🧰 Capacidades de Igris (herramientas)`, `▶️ Despliegue`, `🔐 Las dos superficies de acceso`, `🚀 Características`, `⚙️ Variables de entorno (Coolify)`, `pwa.js`?**
  _High betweenness centrality (0.221) - this node is a cross-community bridge._
- **Are the 77 inferred relationships involving `User` (e.g. with `authenticate_user()` and `get_user_by_id()`) actually correct?**
  _`User` has 77 INFERRED edges - model-reasoned connections that need verification._
- **What connects `claude-mem`, `@tauri-apps/cli`, `igris-chat` to the rest of the system?**
  _6 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `UserChat.vue` be split into smaller, more focused modules?**
  _Cohesion score 0.0482897384305835 - nodes in this community are weakly interconnected._
- **Why does `📲 Instalable como aplicación (PWA)` connect `pwa.js` to `⚔️ IGRIS - Asistente de IA con Avatar, Voz, Chat Web y Telegram`?**
  _High betweenness centrality (0.214) - this node is a cross-community bridge._
- **Should `device_routes.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05314685314685315 - nodes in this community are weakly interconnected._
- **Why does `syncManifest()` connect `pwa.js` to `App.vue`?**
  _High betweenness centrality (0.214) - this node is a cross-community bridge._