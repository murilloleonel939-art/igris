; Ganchos del instalador NSIS de IGRIS Chat.
; Tauri los inyecta en su plantilla mediante "installerHooks".
;
; Objetivo: que la desinstalación deje el PC exactamente como estaba.

!macro NSIS_HOOK_PREINSTALL
  ; Quita un arranque automático de una instalación anterior antes de reinstalar.
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "IGRIS"
!macroend

!macro NSIS_HOOK_POSTINSTALL
  ; Acceso directo en el menú Inicio para abrir el chat.
  CreateShortcut "$SMPROGRAMS\${PRODUCTNAME}.lnk" "$INSTDIR\${MAINBINARYNAME}.exe"

  ; Acceso directo visible al desinstalador, además del de Aplicaciones instaladas.
  CreateShortcut "$SMPROGRAMS\Desinstalar ${PRODUCTNAME}.lnk" "$INSTDIR\uninstall.exe"

  ; Arranque automático al iniciar sesión, activo desde la propia instalación
  ; (no solo tras el primer lanzamiento de la app).
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "IGRIS" '"$INSTDIR\${MAINBINARYNAME}.exe"'
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  ; Quita el arranque automático: sin esto, Windows intentaría abrir un
  ; ejecutable que ya no existe en cada inicio de sesión.
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "IGRIS"

  ; Elimina los accesos directos creados por este instalador.
  Delete "$SMPROGRAMS\${PRODUCTNAME}.lnk"
  Delete "$SMPROGRAMS\Desinstalar ${PRODUCTNAME}.lnk"
  Delete "$DESKTOP\${PRODUCTNAME}.lnk"
!macroend

!macro NSIS_HOOK_POSTUNINSTALL
  ; Borra los datos locales del WebView2. Ahí queda guardada la clave de acceso
  ; del chat y la sesión del usuario: no deben sobrevivir a la desinstalación.
  ;
  ; El desinstalador de Tauri se ejecuta desde una copia en %TEMP%, por eso se
  ; usa la ruta explícita de datos de la aplicación y no $INSTDIR.
  RMDir /r "$LOCALAPPDATA\com.zottagroup.igris.chat"
  RMDir /r "$APPDATA\com.zottagroup.igris.chat"

  ; Borra la carpeta de instalación si quedó vacía tras retirar los archivos.
  RMDir "$INSTDIR"
!macroend
