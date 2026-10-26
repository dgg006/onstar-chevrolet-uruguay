# OnStar Chevrolet Uruguay

<img src="https://raw.githubusercontent.com/dgg006/onstar-chevrolet-uruguay/main/custom_components/onstar_uy/brand/icon.png" alt="Icono de OnStar Chevrolet Uruguay" width="96" height="96">

Integración comunitaria de Chevrolet OnStar para Home Assistant, instalable mediante HACS.

**Probada con el servidor de OnStar de Uruguay. La compatibilidad con otros países de Latinoamérica no está comprobada.** Las funciones disponibles dependen del vehículo, la cuenta y el plan contratado. No es una integración oficial de GM, Chevrolet ni OnStar.

## Configuración del cliente móvil

Los valores compartidos del cliente de myChevrolet Android **8.19.0** vienen preconfigurados en `custom_components/onstar_uy/app_client.json`. Son valores extraídos de la aplicación, separados de las credenciales de cada cuenta. Pueden cambiar entre versiones del APK y se desconoce hasta cuándo serán aceptados. Se pueden reemplazar desde **Reconfigurar → Configuración avanzada**. Consultar la [guía del cliente móvil](docs/CLAVE-CLIENTE.md).

## Funciones

- Combustible, autonomía, kilometraje, aceite y otros diagnósticos disponibles.
- Ubicación y solicitud de actualización de datos al vehículo.
- Bloquear y desbloquear puertas.
- Activar y detener destellos de luces y bocina.
- Sensores experimentales de ventanas y cierres, que muestran desconocido si no hay datos.

Los comandos de luces y bocina usan la duración predeterminada de la app. Los botones de apagado permiten detenerlos antes y comparten la orden de cancelación, que puede detener ambas acciones. Una orden no se reenvía automáticamente si su resultado es incierto.

El resultado de una orden de bloqueo no se presenta como el estado actual de las puertas. Los sensores de presión recomendada no representan presión medida de neumáticos. Los campos ausentes no se convierten en cero ni en cerrado; las referencias en cero recibidas del servidor tampoco acreditan una medición de presión.

## Requisitos

- Home Assistant 2026.10.0 o posterior.
- HACS instalado y configurado, para la instalación desde HACS.
- Cuenta de myChevrolet con el vehículo asociado y un plan OnStar que habilite las funciones utilizadas.

## Instalación con el botón de HACS

[![Abrir repositorio en HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=dgg006&repository=onstar-chevrolet-uruguay&category=integration)

1. Pulsar el botón y elegir la dirección de tu Home Assistant si se solicita.
2. Confirmar la incorporación del repositorio en HACS.
3. Descargar **OnStar Chevrolet Uruguay** y reiniciar Home Assistant.
4. Continuar con la configuración indicada más abajo.

El botón abre el repositorio personalizado en HACS; la descarga requiere confirmación. Si no abre tu instancia, utilizar los pasos manuales. Añadirlo como repositorio personalizado no implica que esté incluido en el catálogo predeterminado de HACS.

## Instalación manual en HACS

1. Abrir HACS y entrar en el menú de **Repositorios personalizados**.
2. Agregar `https://github.com/dgg006/onstar-chevrolet-uruguay`.
3. Seleccionar la categoría **Integración** y confirmar.
4. Buscar **OnStar Chevrolet Uruguay**, descargar y reiniciar Home Assistant.

## Configuración

1. Ir a **Ajustes → Dispositivos y servicios → Agregar integración**.
2. Buscar **OnStar Chevrolet Uruguay**.
3. Ingresar el correo y la contraseña de myChevrolet; no hace falta modificar la configuración avanzada.
4. Si hay un solo vehículo, se selecciona automáticamente. Si hay varios, elegir uno de la lista.

No requiere ingresar el VIN manualmente, configurar MQTT ni usar un emulador. No pide PIN: el acceso regional y los controles se comprobaron sin él. Las cuentas que exijan otro método de autenticación todavía no están verificadas. Esta versión permite una cuenta y un vehículo seleccionado por instancia.

Las instalaciones anteriores conservan su configuración. También se admite el archivo opcional `onstar_uy_private.json`; una modificación explícita desde la configuración avanzada tiene prioridad. Las modificaciones guardadas en Home Assistant sobreviven a las actualizaciones por HACS. No incluir información de la cuenta o el vehículo en archivos de distribución ni incidencias.

## Actualización y opciones

En instalaciones nuevas, los datos se solicitan al vehículo cada 30 minutos. Las instalaciones existentes conservan su intervalo configurado. El botón **Actualizar datos** permite una solicitud manual. El servidor puede entregar información anterior: cada lectura conserva la fecha informada por el vehículo.

Si OnStar rechaza las credenciales, Home Assistant detiene los reintentos automáticos y solicita ingresar nuevamente la contraseña. Se conservan el vehículo y los ajustes existentes. Los errores de conexión se reintentan sin solicitar otra contraseña.

Desde **Reconfigurar** se puede cambiar la contraseña, el intervalo —mínimo 5 minutos— y la solicitud automática de datos nuevos. Si esta última se desactiva, se siguen consultando los datos guardados por GM y se conserva el botón de actualización manual.

En **Configuración avanzada** se puede ajustar el identificador, la clave y la versión de la aplicación. Cambiar el identificador exige ingresar su clave correspondiente. La clave se muestra oculta y vacía en el formulario: dejarla vacía conserva la actual. Antes de guardar se valida el acceso y que el vehículo siga perteneciendo a la cuenta, sin enviar comandos. Si falla, la configuración anterior permanece intacta. El icono del auto está incluido en la integración.

Los decimales de presentación se pueden ajustar en Home Assistant; los valores almacenados mantienen su precisión.

## Compatibilidad y limitaciones

| Función | Estado |
|---|---|
| Acceso al servidor de Uruguay | Comprobado |
| Diagnósticos, ubicación y actualización | Comprobados |
| Comandos de puertas, luces y bocina | Comprobados |
| Lectura del estado de ventanas y bloqueos | Experimental; sin datos en el vehículo de prueba |
| Otros modelos, planes y cuentas | Depende de los datos y permisos que entregue OnStar |
| Otros países de Latinoamérica | Sin verificar |

Que el servidor anuncie una capacidad no garantiza que entregue una lectura. Los sensores experimentales se pueden desactivar individualmente.

## Demoras y errores de OnStar

- Los controles pueden tardar más de un minuto. La integración espera hasta 180 segundos y consulta el resultado cada 5 segundos; no vuelve a enviar la orden física.
- Un resultado no confirmado no equivale a que el auto esté bloqueado o desbloqueado. Comprobar el vehículo si la acción es importante.
- Si aparece HTTP 429, el servicio está limitando solicitudes. Evitar pulsar repetidamente, aumentar el intervalo o desactivar temporalmente la solicitud automática de datos nuevos desde Reconfigurar.
- Si también falla myChevrolet, comprobar cobertura, estado del servicio y permisos del plan. Cambiar la configuración del cliente no soluciona por sí solo un problema de comunicación con el vehículo.
- Las fechas de las lecturas corresponden a los datos entregados por GM, que pueden ser anteriores a la última consulta.

## Desinstalación

Eliminar la entrada de OnStar Chevrolet Uruguay en Ajustes → Dispositivos y servicios. Después se pueden quitar sus archivos desde HACS y reiniciar Home Assistant. Esto elimina la configuración de esta integración en HA; no cancela la cuenta ni el plan de OnStar.

## Instalación sin HACS

Copiar `custom_components/onstar_uy` a la carpeta `custom_components` de Home Assistant, reiniciar y agregar la integración desde la interfaz.

## Reconocimientos

Durante el desarrollo se consultaron estos proyectos para contrastar rutas de la API, formatos de comandos, seguimiento de solicitudes, tiempos de espera y límites de consulta:

- [BigThunderSR/OnStarJS](https://github.com/BigThunderSR/OnStarJS): referencia técnica sobre comandos y respuestas de OnStar.
- [BigThunderSR/onstar2mqtt](https://github.com/BigThunderSR/onstar2mqtt): referencia sobre el funcionamiento de las consultas, las demoras y los límites del servicio.
- [samrum/OnStarJS](https://github.com/samrum/OnStarJS): biblioteca original y antecedente del trabajo comunitario sobre la API.

Gracias a sus autores y colaboradores por compartir su trabajo y documentar el comportamiento de OnStar. La investigación de la autenticación y del servicio regional uruguayo se realizó también mediante el análisis de myChevrolet y comprobaciones con un vehículo real.

### Asistencia de IA

Esta integración se desarrolló con asistencia de **ChatGPT (OpenAI)** para investigar el protocolo regional, escribir y revisar código, preparar pruebas y redactar documentación. Las comprobaciones de los controles con el vehículo real se realizaron con la colaboración de su propietario.

## Privacidad y soporte

Las credenciales personales se guardan en la configuración de tu Home Assistant y se envían a GM mediante HTTPS. Los tokens se conservan en memoria. No se registran contraseñas, tokens ni cuerpos de respuesta.

Para informar un problema, indicar versiones, país y mensaje de error, sin contraseñas, tokens, VIN ni ubicación. Consultar [SECURITY.md](SECURITY.md) y [CHANGELOG.md](CHANGELOG.md).

Los nombres Chevrolet y OnStar y el emblema de Chevrolet identifican los servicios compatibles y no implican afiliación ni aprobación de sus propietarios. La licencia del código no concede derechos sobre esas marcas.
