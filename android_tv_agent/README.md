# IGRIS TV Agent

Agente Android independiente para TV Box con Android 10–14 (API 29–35), pensado para equipos como X88 Pro 10, MX10 y firmwares AOSP/Android TV compatibles. No comparte código ni credenciales con el agente Windows.

## Emparejamiento

1. El usuario autenticado genera el código desde **Conexiones → Mi TV Box** en IGRIS (`POST /api/user/tvbox/pairing-codes`). El código queda ligado a su cuenta en el servidor.
2. En la aplicación se introduce el código (mínimo 6 caracteres) y la URL `wss://igris.zottagroup.com/api/tvbox/ws`.
3. El servidor valida que el código no esté usado ni caducado, registra el equipo y devuelve una credencial `tvbox_...`.
4. El agente guarda la credencial cifrada con `EncryptedSharedPreferences` y la usa en las reconexiones posteriores.

El código corto es temporal y de un solo uso. No sustituye a la credencial permanente.

## Acciones admitidas

- `launch_app`: abrir una aplicación instalada por nombre de paquete.
- `device_info`: modelo, fabricante y versión de Android.
- `volume`: subir, bajar, silenciar o fijar el nivel multimedia.
- `key`: BACK, HOME y RECIENTES mediante el servicio de accesibilidad.

Para `key`, el usuario debe habilitar **TV Agent** en Ajustes → Accesibilidad del TV Box. Sin ese permiso el resto de funciones sigue operando. La disponibilidad exacta depende del firmware del equipo.

## Conexión

El agente abre un WebSocket saliente y lo mantiene con un ping cada 30 segundos, un heartbeat de la aplicación y reconexión con espera creciente (2 s hasta 60 s). Un servicio en primer plano mantiene la conexión viva cuando la aplicación pasa a segundo plano. No se abre ningún puerto en el TV Box ni se expone ADB a internet.

## Compilación

El APK lo compila GitHub Actions con `.github/workflows/build-tv-agent.yml`: JDK 17, Android SDK API 35 y Gradle 8.9. El workflow se dispara al cambiar `android_tv_agent/**`, publica el artefacto `IgrisTvAgent` y copia el APK a `web/public/downloads/IgrisTvAgent.apk` para que los usuarios lo descarguen desde **Conexiones → Mi TV Box**.

Para compilar en local, abrir esta carpeta en Android Studio actualizado y ejecutar `assembleDebug`. No se incluye el wrapper de Gradle.
