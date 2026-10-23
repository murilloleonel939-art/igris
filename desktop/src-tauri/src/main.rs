#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::Manager;

// Único dominio que la ventana puede cargar. Cualquier otro enlace se bloquea,
// así que la ventana no puede salir del chat ni llegar al panel de administración.
const CHAT_HOST: &str = "webigris.zottagroup.com";

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            // El arranque automático con Windows lo registra el instalador
            // (windows/hooks.nsh) y lo elimina el desinstalador, para que ambos
            // queden siempre coherentes.
            if let Some(window) = app.get_window("main") {
                let _ = window.show();
            }
            Ok(())
        })
        // La ventana solo puede permanecer en el chat publicado.
        .on_navigation(|url| match url.scheme() {
            "https" => url.host_str() == Some(CHAT_HOST),
            // Recursos y pantallas locales que embebe el propio ejecutable.
            "tauri" | "asset" | "about" | "data" => true,
            _ => false,
        })
        .build(tauri::generate_context!())
        .expect("no se pudo iniciar la ventana de IGRIS")
        .run(|_handle, _event| {});
}
