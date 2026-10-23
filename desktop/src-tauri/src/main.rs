#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::{Manager, Url, WebviewUrl, WebviewWindowBuilder};

// Único dominio que la ventana puede cargar. Cualquier otro enlace se bloquea,
// así que la ventana no puede salir del chat ni llegar al panel de administración.
const CHAT_URL: &str = "https://webigris.zottagroup.com";
const CHAT_HOST: &str = "webigris.zottagroup.com";

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let url = Url::parse(CHAT_URL)?;

            WebviewWindowBuilder::new(app, "main", WebviewUrl::External(url))
                .title("IGRIS")
                .inner_size(1280.0, 820.0)
                .min_inner_size(900.0, 640.0)
                .center()
                // Micrófono, altavoz y cámara del equipo, sin diálogo de permisos,
                // y audio automático para que la voz de Igris suene sin pulsar nada.
                .additional_browser_args(
                    "--disable-features=msWebOOUI,msPdfOOUI,msSmartScreenProtection \
                     --use-fake-ui-for-media-stream \
                     --autoplay-policy=no-user-gesture-required",
                )
                // La ventana solo puede permanecer en el chat publicado.
                .on_navigation(|url| match url.scheme() {
                    "https" => url.host_str() == Some(CHAT_HOST),
                    // Recursos locales que embebe el propio ejecutable.
                    "tauri" | "asset" | "about" | "data" => true,
                    _ => false,
                })
                .build()?;

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("no se pudo iniciar la ventana de IGRIS");
}
