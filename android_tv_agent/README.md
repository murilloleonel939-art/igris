# IGRIS TV Agent

Agente Android independiente para TV Box con Android 10–14 (API 29–35), pensado para equipos como X88 Pro 10, MX10 y firmwares AOSP/Android TV compatibles.

## Emparejamiento

1. En IGRIS se genera un código temporal de 8 caracteres desde `POST /api/tvbox/pairing-codes`.
2. En la aplicación se introduce el código (mínimo 6 caracteres) y la URL `wss://igris.zottagroup.com/api/tvbox/ws`.
3. El servidor entrega una credencial `tvbox_...`; el agente la guarda cifrada y la usa en reconexiones posteriores.

El código corto es temporal y de un solo uso. No sustituye a la credencial permanente.

## Acciones previstas

- Abrir aplicaciones instaladas por nombre de paquete.
- Consultar información del dispositivo y versión de Android.
- Ajustar volumen multimedia.
- Navegación global opcional mediante el servicio de accesibilidad de Android.

Para la navegación, el usuario debe habilitar `Igris TV Agent` en Ajustes → Accesibilidad. La disponibilidad exacta depende del firmware del TV Box.

## Compilación

Abrir esta carpeta en Android Studio actualizado y ejecutar `assembleDebug` o `assembleRelease`. No se incluye un `gradlew` generado y la compilación no se ejecutó en este entorno porque no hay Gradle instalado.
