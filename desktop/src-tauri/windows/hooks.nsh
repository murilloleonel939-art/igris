; Ganchos del instalador NSIS de IGRIS Chat (Tauri 2).
; Tauri los inyecta en su plantilla mediante "installerHooks".
;
; Objetivo: que instalar y desinstalar dejen el PC siempre coherente.

!macro NSIS_HOOK_PREINSTALL
  ; Quita un arranque automático de una instalación anterior antes de reinstalar.
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "IGRIS"
!macroend

!macro NSIS_HOOK_POSTINSTALL
  ; Acceso directo visible al desinstalador, junto al del chat
  ; ($SMPROGRAMS\IGRIS\IGRIS.lnk lo crea la propia plantilla de Tauri).
  CreateShortcut "$SMPROGRAMS\IGRIS\Desinstalar IGRIS.lnk" "$INSTDIR\uninstall.exe"

  ; Arranque automático al iniciar sesión, activo desde la propia instalación.
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "IGRIS" '"$INSTDIR\${MAINBINARYNAME}.exe"'
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  ; Quita el arranque automático.
  ; (La plantilla de Tauri también lo borra, pero solo si no se está actualizando.)
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "IGRIS"

  ; Elimina el acceso directo al desinstalador. Debe hacerse antes de que la
  ; plantilla borre la carpeta del menú Inicio, o la carpeta queda vacía.
  Delete "$SMPROGRAMS\IGRIS\Desinstalar IGRIS.lnk"
!macroend

!macro NSIS_HOOK_POSTUNINSTALL
  ; Borra los datos locales del WebView2, donde quedan la clave de acceso al
  ; chat y la sesión del usuario. No deben sobrevivir a la desinstalación.
  ;
  ; Se omite al actualizar ($UpdateMode = 1): ahí interesa conservar la sesión.
  ${If} $UpdateMode <> 1
    RMDir /r "$LOCALAPPDATA\com.zottagroup.igris.chat"
    RMDir /r "$APPDATA\com.zottagroup.igris.chat"
  ${EndIf}
!macroend
