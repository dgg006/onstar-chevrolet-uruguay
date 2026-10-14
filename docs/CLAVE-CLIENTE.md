# Configuración del cliente móvil

## Valores predeterminados

`custom_components/onstar_uy/app_client.json` contiene únicamente `client_id`,
`client_secret` y `app_version` de myChevrolet Android 8.19.0. No contiene datos
personales. Al instalar normalmente sólo se pide correo y contraseña de la cuenta.

La comparación estática de 8.1.0, 8.11.0, 8.17.0 y 8.19.0 encontró claves diferentes.
Las parejas de 8.11.0 y 8.19.0 permitieron autenticación y consultas de diagnóstico
en el servidor de Uruguay. Esto no demuestra que las claves cambien en cada
actualización ni que las anteriores hayan sido revocadas. Se desconoce su vigencia
futura. Un error puede deberse también a la cuenta, conexión o cambios del servicio.

## Cambiar desde Home Assistant

1. Abrir Ajustes → Dispositivos y servicios → OnStar Chevrolet Uruguay.
2. En el menú de la entrada, elegir Reconfigurar.
3. Desplegar Configuración avanzada.
4. Ingresar el identificador y su clave de la misma versión del APK, junto con
   la versión de la aplicación (por ejemplo, 8.19.0).
5. Guardar. Se comprueba el acceso y la presencia del vehículo mediante consultas
   de lectura. Si falla, no se guarda ningún cambio.

La clave se muestra como campo oculto y sin valor precargado. Dejarla vacía
conserva la actual; cambiar el identificador exige ingresar también su clave.
La versión se aplica a los encabezados de las solicitudes. La integración se
recarga después de una validación exitosa. Se conservan entidades y automatizaciones.

Los ajustes guardados en Home Assistant tienen prioridad y sobreviven a HACS.
Editar el JSON distribuido cambia los predeterminados; HACS puede reemplazar ese
archivo y no modifica una pareja guardada explícitamente desde la interfaz.

## Compatibilidad con archivos privados anteriores

Se admite `onstar_uy_private.json` junto a `configuration.yaml`, con estos campos:

```json
{
  "client_id": "",
  "client_secret": "",
  "app_version": ""
}
```

Completar los tres campos con valores correspondientes a la misma versión.
Los archivos antiguos que sólo contenían client_secret siguen siendo compatibles
con el identificador y versión previamente configurados. El archivo se vuelve a
leer al iniciar sesión; recargar aplica el cambio inmediatamente.

Prioridad: ajuste explícito de la UI → archivo privado → configuración anterior
de la entrada → valores distribuidos. Un archivo existente pero inválido produce
un error y no usa silenciosamente los predeterminados. Se puede corregir desde
la UI proporcionando una pareja válida completa.

## Qué se busca en el APK

Se busca la **clave de firma del cliente móvil**, identificada como `client_secret` en la configuración de la aplicación regional. No es una contraseña de cuenta, un PIN, un token de sesión ni un secreto TOTP.

El antecedente comprobado corresponde a **myChevrolet Android 8.19.0**, paquete `com.gm.chevrolet.nomad.ownership`, con el código JavaScript compilado en un bundle de Hermes. La configuración aparecía en una función de inicialización —identificada como función 1634 en esa compilación—, asociada al cliente `OMB_CVY_AND_8T0`.

La relación que permite identificarla es:

- Un objeto de configuración con `client_id` y `client_secret`, correspondiente al cliente regional de producción.
- Uso de esa clave para firmar un JWS mediante **HMAC-SHA256 / HS256**.
- Envío de la solicitud firmada a `/api/v1/oauth/token` en `https://api.lam.ext.gm.com`.
- Datos de autenticación de la solicitud separados de la configuración de la aplicación: usuario, contraseña, identificador de dispositivo, nonce, fecha y grant type.

En la compilación analizada el valor tenía 32 caracteres, pero la longitud por sí sola no permite identificarlo ni debe asumirse para futuras versiones. La función, el formato del bundle, el identificador de cliente y el flujo de autenticación pueden cambiar. Buscar sólo una cadena de esa longitud no es suficiente.

No se garantiza que un APK futuro contenga la clave como un literal ni que mantenga el mismo flujo. Si no se puede establecer la relación con el proceso de firma, el análisis debe concluir que no se pudo identificar, sin inventar una clave.

## Texto para solicitar el análisis a una IA

```text
Analizá el APK de myChevrolet que adjunto y determiná si contiene la configuración
para el cliente regional de OnStar Uruguay. No necesito datos de mi cuenta.

Busco el client_secret utilizado como clave HMAC-SHA256 para firmar solicitudes
JWS/HS256 enviadas a https://api.lam.ext.gm.com/api/v1/oauth/token. Como referencia,
en myChevrolet Android 8.19.0, paquete com.gm.chevrolet.nomad.ownership, se encontró
junto al client_id OMB_CVY_AND_8T0 en una configuración de inicialización del código
Hermes. La función 1634 y la longitud de 32 caracteres son referencias de esa
compilación, no ubicaciones ni formatos garantizados para otra versión.

Comprobá la relación entre el valor candidato, la configuración de producción y
la función que firma la solicitud. No lo confundas con un token, PIN, contraseña,
clave TOTP, identificador público de cliente o configuración de otro entorno.

Informá la versión del APK y la ubicación o función que aporta la evidencia.
Si no podés demostrar qué valor se usa para firmar, decí que no pudo identificarse.
No pruebes cuentas ni envíes comandos al vehículo.

Informá la pareja client_id / client_secret y la versión app_version, sin datos
de cuentas. Se cargarán en la configuración avanzada de Home Assistant. No
incluyas correo, contraseña, PIN, VIN, coordenadas ni tokens de sesión.
```

La capacidad de realizar este análisis depende de las herramientas disponibles para la IA y de la estructura del APK. Identificar una clave no demuestra por sí solo que todos los modelos, cuentas o países sean compatibles.

## Privacidad

Las credenciales de cuenta se configuran por separado y no forman parte del JSON
distribuido. No publicar archivos privados de Home Assistant, sus copias de
seguridad, capturas de tráfico ni información de la cuenta o del vehículo.
