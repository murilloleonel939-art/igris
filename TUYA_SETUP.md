# Configuración de Tuya para Igris

Cada usuario conecta su propia cuenta de Smart Life desde **`/u/conexiones` → «Mi casa»**.
Ahí pega su **Access ID**, su **Access Secret** y el **UID** de su cuenta, y pulsa
**«Guardar y comprobar»**. Igris prueba los datos contra Tuya antes de guardarlos, los
cifra con una clave derivada de `SECRET_KEY` y desde entonces firma con ellos las
llamadas de ese usuario.

Los datos se obtienen en [iot.tuya.com](https://iot.tuya.com), en el proyecto de Cloud
de cada usuario:

| Dato | Dónde |
| --- | --- |
| Access ID | *Cloud* → *Development* → pestaña **Authorization** |
| Access Secret | La misma pestaña |
| UID | *Cloud* → *Devices* → *Device List*, en el detalle de la cuenta |

La cuenta de Tuya tiene que estar enlazada con Smart Life desde *Devices → Link App
Account*, o no aparecerá ningún dispositivo. Para los mandos infrarrojos hay que
habilitar **IR Control Hub Open Service**.

## Variables del servidor (opcionales)

```env
TUYA_ACCESS_ID=...
TUYA_ACCESS_SECRET=...
TUYA_REGION=us
# Opcional: limita el acceso a IDs concretos; si se omite, se usan los vinculados
# TUYA_DEVICE_IDS=id_del_ir,id_del_aire,id_del_tv
```

Estas variables ya no son necesarias: solo se usan como respaldo cuando un usuario
todavía no ha guardado sus propias credenciales. Con todos los usuarios configurados
desde IGRIS se pueden borrar de Coolify.

Recuerda activar la función **Casa inteligente (Tuya / Smart Life)** para cada usuario
desde `/panel/usuarios` → **«Permisos»**; sin ese permiso la sección no aparece.
