# Graph Report - igrisfase3  (2026-10-23)

## Corpus Check
- 126 files · ~189,740 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 27 file(s) not represented in the graph (top: .exe 6, (none) 5, .xml 4)

## Summary
- 2316 nodes · 4914 edges · 129 communities (96 shown, 33 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 376 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `bbe5bc5f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- UserChat.vue
- device_routes.py
- knowledge_graph.py
- asyncio
- TvAgentService
- scheduler.py
- Session
- httpx
- App.vue
- tuya.py
- spotify.py
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
- vue
- Configuration.vue
- auth.py
- 🧰 Capacidades de Igris (herramientas)
- auth_routes.py
- stt.py
- user_voice_ws
- homeassistant.py
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
- main
- push-to-github.js
- IgrisAvatar.vue
- TelegramLink
- typing
- client_voice.py
- process_telegram_update
- desktop/package.json
- web/package.json
- server.js
- TvAccessibilityService
- login
- SessionStore
- tts.py
- client_speak.py
- 🚀 IGRIS Frontend - Deployment Checklist
- generate_icons.py
- run_tests.sh
- 🔮 IGRIS Web Platform - Setup Completo
- capabilities.py
- .save
- settings_manager.py
- Archivos de `core/tools/`
- IGRIS_PLAN.md
- BLOQUE F — Voz robusta
- verify_2fa
- _system_message
- BLOQUE A — Estabilizar la caída
- IGRIS Chat — ventana de escritorio para Windows
- 🚀 Características
- Brain
- 📱 Integración WhatsApp (Meta Cloud API)
- IGRIS TV Agent
- _StreamFunction
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
- BLOQUE D — Higiene
- verify_deployment.sh
- 1. Obtener credenciales en Meta
- 🚀 Instalación Backend (FastAPI)
- 🐛 Troubleshooting
- BLOQUE B — Ver
- BLOQUE E — Pool
- 🐳 Deploy en Coolify (EC2)
- 📊 Endpoints API
- Agente local de IGRIS para Windows
- get_me
- AGENTS.md
- verify_token
- get_db
- push_to_github.sh script
- call_igris_chat
- TUYA_SETUP.md
- verify_and_fix.sh
- sw.js
- igris-chat

## God Nodes (most connected - your core abstractions)
1. `Session` - 111 edges
2. `User` - 86 edges
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

## Communities (129 total, 33 thin omitted)

### Community 0 - "UserChat.vue"
Cohesion: 0.04
Nodes (69): setIgrisState(), listenOnce(), cancelMemory(), cancelNewMemory(), chatBox, chatInput, chatMessages, confirmRelation() (+61 more)

### Community 1 - "device_routes.py"
Cohesion: 0.05
Nodes (35): AgentToken, TvBoxPairingCode, TvBoxToken, AgentTokenCreate, AgentTokenLink, create_agent_token(), delete_agent_token(), device_program_access() (+27 more)

### Community 2 - "knowledge_graph.py"
Cohesion: 0.07
Nodes (36): KnowledgeNode, KnowledgeRelation, utcnow(), _apply_corrections(), _backfill_node_embeddings(), _bounded(), _clean_object(), confirm_graph_relation() (+28 more)

### Community 3 - "asyncio"
Cohesion: 0.07
Nodes (28): Note, _asked_to_delete(), check_delete(), format_date_local(), format_local(), local_to_utc(), normalize(), register_delete() (+20 more)

### Community 4 - "TvAgentService"
Cohesion: 0.06
Nodes (5): MainActivity, SecurePrefs, LocalBinder, TvAgentService, WebSocketListener

### Community 5 - "scheduler.py"
Cohesion: 0.05
Nodes (19): Reminder, _add_months(), build_message(), _claim_due(), _configured_whatsapp_destination(), _read(), _confirm(), _deliver() (+11 more)

### Community 6 - "Session"
Cohesion: 0.06
Nodes (33): create_user(), get_user_by_username(), hash_password(), Session, User, export_graph(), save_graph(), model_status() (+25 more)

### Community 7 - "httpx"
Cohesion: 0.09
Nodes (26): confirm_event(), confirm_reschedule(), delete_event(), _fmt(), is_affirmative(), _normalize(), propose_event(), propose_reschedule() (+18 more)

### Community 8 - "App.vue"
Cohesion: 0.07
Nodes (43): axios, vue-router, api, clearKey(), getKey(), setKey(), ADMIN_ROUTES, displayInitials (+35 more)

### Community 9 - "tuya.py"
Cohesion: 0.09
Nodes (31): _allowed_device(), AmbiguousTuyaDeviceError, _call(), _coerce_value(), _config(), _configured_device_ids(), control_tuya_device(), _device_functions() (+23 more)

### Community 10 - "spotify.py"
Cohesion: 0.07
Nodes (31): decrypt(), encrypt(), _fernet(), SpotifyAccount, add_tracks_to_spotify_playlist(), authorization_url(), client_config(), create_spotify_playlist() (+23 more)

### Community 11 - "user_routes.py"
Cohesion: 0.07
Nodes (30): import_graph(), preview_graph_import(), validate_graph_payload(), bind_sessions(), _clear_fails(), _client_ip(), confirm_user_graph_relation(), constant_time_check() (+22 more)

### Community 12 - "⚔️ IGRIS - Asistente de IA con Avatar, Voz, Chat Web y Telegram"
Cohesion: 0.04
Nodes (45): Acceso, Agente Android TV Box, Agente local de Windows, Base de datos, Cambiar el video del avatar, Configuración recomendada en Coolify, Crear archivos en el PC (`create_document`), 🙏 Créditos (+37 more)

### Community 13 - "AdminUsers.vue"
Cohesion: 0.08
Nodes (34): activeTab, adminUnlinkTelegram(), cancelAdminMemory(), createAdminMemory(), createUser(), defaultFeatures(), deleteAdminMemory(), features (+26 more)

### Community 14 - "main.py"
Cohesion: 0.07
Nodes (21): _admin_user_from_bearer(), admin_voice_chat(), AIConfigResponse, AIConfigUpdate, auth_check(), ChatRequest, get_ai_config(), get_stt_config() (+13 more)

### Community 15 - "🚀 IGRIS - Deployment Summary (October 4, 2024)"
Cohesion: 0.05
Nodes (41): 1. Push a GitHub, 2. Crear App en Coolify, 3. Configurar Reverse Proxy, 4. Deploy, 5. Verificar Funcionamiento, Antes (Oct 3), Archivo server.js, Archivos Existentes (Backend) (+33 more)

### Community 16 - "errorMessage"
Cohesion: 0.07
Nodes (41): errorMessage(), agentTokens, allowedPrograms, createToken(), deleteToken(), error, fixedPrograms, linking (+33 more)

### Community 17 - "os"
Cohesion: 0.09
Nodes (18): _clean_chain(), get_active_provider(), get_active_provider_config(), get_api_base(), get_api_key(), get_available_providers(), get_default_config(), get_fallback_chain() (+10 more)

### Community 18 - "WhatsAppClient"
Cohesion: 0.09
Nodes (11): _configured_destination(), send_whatsapp_message(), send_test_message(), WhatsAppAPIError, WhatsAppClient, WhatsAppConfigurationError, Comprobar que funciona, Destinatario (+3 more)

### Community 19 - "Plan de Arreglo IGRIS — Escalado para 100+ usuarios"
Cohesion: 0.06
Nodes (33): 1.1 — Red de seguridad: cambiar a Deepgram (5 min, reversible), 1.2 — Caché persistente de modelos STT, 1.3 — Warmup STT en startup (agnóstico al motor), 1.4 — Cola de STT con workers paralelos configurable (CRÍTICO para 100+ usuarios), 1.6 — Lock por motor para evitar carga duplicada, 2.1 — Reestructurar WebSocket para no retener conexión, 2.2 — Aumentar pool BD dramáticamente, 2.3 — Redis para sesiones (persistencia + escalabilidad) (+25 more)

### Community 20 - "GoogleAccount"
Cohesion: 0.09
Nodes (19): admin_capabilities(), capabilities_from_user(), GoogleAccount, forget_token(), oauth_configured(), redirect_uri(), scopes_for(), _bind_identity() (+11 more)

### Community 21 - "BaseModel"
Cohesion: 0.08
Nodes (14): admin_create_user_memory(), admin_list_user_memories(), admin_update_user_memory(), create_user_memory(), GraphRelationStatusIn, list_user_memories(), _memory_json(), MemoryCreateIn (+6 more)

### Community 22 - "🚀 IGRIS Coolify Deployment - Step by Step"
Cohesion: 0.06
Nodes (34): 3.1 - New Application, 3.2 - Configuración Básica, 3.3 - Build Settings, 3.4 - Environment Variables, 3.5 - Recursos (Opcional), 3.6 - Health Check (Opcional), 5.1 - Acceso al Frontend, 5.2 - Verificar Conexión al Backend (+26 more)

### Community 23 - "e2e_users.py"
Cohesion: 0.08
Nodes (11): denial_message(), reset_agent_user(), set_agent_user(), run_tool(), _geocode(), get_weather(), _intentos(), preflight() (+3 more)

### Community 24 - "memory.py"
Cohesion: 0.11
Nodes (17): MemoryLink, UserMemory, _backfill_embeddings(), _cosine_similarity(), _decode_embedding(), _embedding_client(), _embedding_for(), extract_memory_candidates() (+9 more)

### Community 25 - "gmail.py"
Cohesion: 0.11
Nodes (16): _build_raw_message(), _clean(), _decode(), _find_part(), _header(), _html_to_text(), list_emails(), fetch() (+8 more)

### Community 26 - "database.py"
Cohesion: 0.08
Nodes (9): AIConfig, _build_engine(), _column_exists(), _ensure_postgres_database_exists(), init_db(), _owner_user_id(), _run_migrations(), _table_exists() (+1 more)

### Community 27 - "profile_routes.py"
Cohesion: 0.12
Nodes (13): Profile, get_current_user(), activate_user(), create_profile(), delete_profile(), get_ai_config(), get_dashboard(), get_or_create_ai_config() (+5 more)

### Community 28 - "nsis"
Cohesion: 0.07
Nodes (29): app, security, windows, withGlobalTauri, build, devUrl, frontendDist, bundle (+21 more)

### Community 29 - "Dashboard.vue"
Cohesion: 0.10
Nodes (25): chatBox, chatInput, chatMessages, FATAL, handsFree, isBusy, isListening, isPlayingTTS (+17 more)

### Community 30 - ".say_stream"
Cohesion: 0.11
Nodes (12): BrainSession, _delta(), _build_client(), _close_client(), _complete_with_anthropic(), _mark_provider_failed(), _mark_provider_ok(), _provider_available() (+4 more)

### Community 31 - "vue"
Cohesion: 0.10
Nodes (22): 📲 Instalable como aplicación (PWA), pinia, vue, isIos, isStandalone, visible, useAudioLevel(), attach() (+14 more)

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

### Community 37 - "user_voice_ws"
Cohesion: 0.11
Nodes (12): neural_memory_context(), ChatIn, register_voice_profile(), _session_key(), transcribe_user_audio(), user_chat(), user_voice_chat(), user_voice_ws() (+4 more)

### Community 38 - "homeassistant.py"
Cohesion: 0.16
Nodes (9): call_homeassistant_service(), control_homeassistant_device_for_session(), get_homeassistant_device_state(), get_homeassistant_device_state_for_session(), list_homeassistant_devices(), list_homeassistant_devices_for_session(), turn_off_device(), turn_on_device() (+1 more)

### Community 39 - "relay.py"
Cohesion: 0.23
Nodes (12): authorized_handler(), wrapper(), authorized_only(), config_cmd(), get_igris_ai_config(), help_cmd(), main(), relay_message() (+4 more)

### Community 40 - "🚀 IGRIS - Deploy en Coolify (Frontend + Backend)"
Cohesion: 0.10
Nodes (20): 📝 Actualizaciones, Backend ✅, 🔧 Cambios Realizados, 📦 Checklist Pre-Deploy, 🏃 Desarrollo Local (localhost), 💡 Desarrollo Local vs Producción, 📋 Estado Actual (Oct 2024), 📁 Estructura de Deploy (+12 more)

### Community 42 - "brain.py"
Cohesion: 0.14
Nodes (8): _anthropic_payload(), _close_stream(), _complete_with_tools(), max_tokens_for(), _stream_chat(), supports_vision(), _tool_content_for_anthropic(), _tool_content_for_openai()

### Community 43 - "🎯 COOLIFY - CONFIGURACIÓN FINAL (FUNCIONA)"
Cohesion: 0.10
Nodes (19): 1️⃣ Abre la App Frontend en Coolify, 2️⃣ Ve a "Build" o "Build Pipeline", 3️⃣ Configura estos campos:, 4️⃣ Runtime / Networking, 5️⃣ Environment Variables, 6️⃣ Deploy, 7️⃣ Espera, 📋 CHECKLIST ANTES DE HACER CLICK EN DEPLOY (+11 more)

### Community 44 - "📊 IGRIS - Resumen del Proyecto v2.0.0"
Cohesion: 0.10
Nodes (19): 📁 Archivos Clave, 🏗️ Arquitectura Final, Backend FastAPI + Autenticación, ✅ COMPLETADO EN ESTA SESIÓN, Documentación, En Coolify, 📊 Estadísticas, Fase 3: Raspberry Pi Sync (+11 more)

### Community 45 - "neural.py"
Cohesion: 0.20
Nodes (11): NeuralExperience, NeuralModelState, _features(), _load_model(), _new_model(), predict_context(), record_experience(), _serialize() (+3 more)

### Community 48 - "google_client.py"
Cohesion: 0.19
Nodes (8): client_config(), Credentials, env_credentials(), _has_stored_account(), _is_admin(), mark_account_error(), resolve_credentials(), stored_credentials()

### Community 49 - "agent.py"
Cohesion: 0.24
Nodes (10): _BITMAPINFO, _BITMAPINFOHEADER, _capture_screen_png(), enumerate_windows(), callback(), execute(), _find_window(), _key_event() (+2 more)

### Community 50 - "main"
Cohesion: 0.16
Nodes (9): configure_token(), save(), enumerate_programs(), load_node_token(), log(), log_path(), main(), save_node_token() (+1 more)

### Community 51 - "push-to-github.js"
Cohesion: 0.21
Nodes (11): createCommit(), createTree(), FILES_TO_UPLOAD, fs, getLastCommit(), https, httpsRequest(), main() (+3 more)

### Community 52 - "IgrisAvatar.vue"
Cohesion: 0.14
Nodes (10): box, cur, failed, LABELS, PROFILE, props, video, caption (+2 more)

### Community 53 - "TelegramLink"
Cohesion: 0.20
Nodes (6): TelegramLink, chat_for_user(), is_linked(), link_chat(), resolve_user(), unlink_chat()

### Community 54 - "typing"
Cohesion: 0.21
Nodes (6): _clean(), make_filename(), normalize_sections(), section_count(), _slug(), create_document()

### Community 55 - "client_voice.py"
Cohesion: 0.26
Nodes (4): main(), play_mp3(), record(), speak()

### Community 56 - "process_telegram_update"
Cohesion: 0.17
Nodes (5): add_csp_header(), _client_ip(), process_telegram_update(), telegram_webhook(), _transcribe_telegram_file()

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
Cohesion: 0.18
Nodes (6): authenticate_user(), create_access_token(), create_refresh_token(), verify_password(), disable_2fa(), login()

### Community 62 - "SessionStore"
Cohesion: 0.20
Nodes (5): SessionStore, BLOQUE G — Escalar, G1 — Redis, G2 — Multi-worker, G3 — Migración a 6 vCPU / 12 GB

### Community 63 - "tts.py"
Cohesion: 0.22
Nodes (4): _get_tts_config(), _load_piper(), reload_config(), synthesize()

### Community 64 - "client_speak.py"
Cohesion: 0.29
Nodes (4): main(), play_mp3(), speak(), main()

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
Cohesion: 0.27
Nodes (3): Capabilities, Feature, tools_for()

### Community 72 - "Archivos de `core/tools/`"
Cohesion: 0.36
Nodes (4): _format(), get_time(), now_context(), Archivos de `core/tools/`

### Community 73 - "IGRIS_PLAN.md"
Cohesion: 0.22
Nodes (8): BLOQUE C — Blindar, C1 — Límites, C2 — Probar el aislamiento, IGRIS — Plan único de arreglo y capacidad, Mapa de bloques, Rollback, Situación de partida, Verificación final

### Community 74 - "BLOQUE F — Voz robusta"
Cohesion: 0.22
Nodes (9): BLOQUE F — Voz robusta, F1 — Cola STT común (`core/stt_queue.py`), F2 — Integrar la cola en todas las rutas de voz, F3 — Deepgram: cliente y semáforo, F4 — Fallback sin bucle, F5 — Verificación de voz por niveles, F6 — Cliente LLM persistente (`core/brain.py:214`), F7 — SQL fuera del event loop (+1 more)

### Community 75 - "verify_2fa"
Cohesion: 0.22
Nodes (4): logout(), register(), setup_2fa(), verify_2fa()

### Community 76 - "_system_message"
Cohesion: 0.25
Nodes (4): _capabilities_of(), _facts_block(), _system_message(), _tools_for_anthropic()

### Community 77 - "BLOQUE A — Estabilizar la caída"
Cohesion: 0.25
Nodes (8): _get_encoder(), A1 — Confirmar la causa, A2 — Lock en `_get_encoder()` (`core/voice.py`), A3 — Locks en las demás cargas diferidas, A4 — Executor acotado, BLOQUE A — Estabilizar la caída, Orden de ejecución, Qué se construye primero

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

### Community 95 - "BLOQUE D — Higiene"
Cohesion: 0.40
Nodes (5): BLOQUE D — Higiene, D1 — Rutas persistentes, D2 — Fuga de temporales en `core/tts.py:93`, D3 — Limpieza automática, D4 — Logs

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

### Community 100 - "BLOQUE B — Ver"
Cohesion: 0.50
Nodes (4): B1 — `/health/deep`, B2 — `/api/stt-stats`, B3 — HEALTHCHECK, BLOQUE B — Ver

### Community 101 - "BLOQUE E — Pool"
Cohesion: 0.50
Nodes (4): BLOQUE E — Pool, E1 — WebSocket sin sesión retenida (`user_routes.py:1302`), E2 — Pool 20+15, E3 — Transacciones

### Community 102 - "🐳 Deploy en Coolify (EC2)"
Cohesion: 0.50
Nodes (4): 1. Dockerfile ya incluido, 2. En Coolify:, 3. Base de Datos en Coolify:, 🐳 Deploy en Coolify (EC2)

### Community 103 - "📊 Endpoints API"
Cohesion: 0.50
Nodes (4): Autenticación, 📊 Endpoints API, Panel de Control, Sistema (Node/RPi)

### Community 104 - "Agente local de IGRIS para Windows"
Cohesion: 0.50
Nodes (3): Agente local de IGRIS para Windows, Instalación desde el ejecutable, Instalación manual

## Knowledge Gaps
- **5 isolated node(s):** `@tauri-apps/cli`, `igris-chat`, `autoprefixer`, `postcss`, `tailwindcss`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1108 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **33 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `⚔️ IGRIS - Asistente de IA con Avatar, Voz, Chat Web y Telegram` connect `⚔️ IGRIS - Asistente de IA con Avatar, Voz, Chat Web y Telegram` to `🧰 Capacidades de Igris (herramientas)`, `vue`, `🚀 Características`?**
  _High betweenness centrality (0.238) - this node is a cross-community bridge._
- **Are the 70 inferred relationships involving `User` (e.g. with `authenticate_user()` and `get_user_by_id()`) actually correct?**
  _`User` has 70 INFERRED edges - model-reasoned connections that need verification._
- **What connects `@tauri-apps/cli`, `igris-chat`, `autoprefixer` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `UserChat.vue` be split into smaller, more focused modules?**
  _Cohesion score 0.043037974683544304 - nodes in this community are weakly interconnected._
- **Why does `📲 Instalable como aplicación (PWA)` connect `vue` to `⚔️ IGRIS - Asistente de IA con Avatar, Voz, Chat Web y Telegram`?**
  _High betweenness centrality (0.230) - this node is a cross-community bridge._
- **Should `device_routes.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05311676909569798 - nodes in this community are weakly interconnected._
- **Why does `syncManifest()` connect `vue` to `App.vue`?**
  _High betweenness centrality (0.230) - this node is a cross-community bridge._