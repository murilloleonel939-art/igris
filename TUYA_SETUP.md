# Configuración de Tuya para Igris

En Coolify añade estas variables al servicio backend:

```env
TUYA_ACCESS_ID=...
TUYA_ACCESS_SECRET=...
TUYA_REGION=us
TUYA_UID=...
TUYA_DEVICE_IDS=id_del_ir,id_del_aire,id_del_tv
```

El secreto se lee únicamente desde variables de entorno. En el panel de administración activa la función **Casa inteligente (Smart Life)** para el usuario que podrá usarla. Los comandos de control requieren que el usuario confirme la acción.
