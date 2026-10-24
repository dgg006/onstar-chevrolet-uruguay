# Cambios

## 0.8.3

- Los rechazos de autenticación detienen los reintentos y solicitan ingresar nuevamente la contraseña.
- Reautenticación desde Home Assistant sin perder el vehículo ni los ajustes guardados.
- Los problemas de conexión conservan sus reintentos y los vehículos ausentes muestran un error de configuración.
- Pruebas de regresión para autenticación, inicio y actualización de datos.

## 0.8.2

- Icono con emblema de Chevrolet en tamaños estándar y alta resolución.
- Validación Hassfest junto a las comprobaciones de HACS y pruebas automáticas.
- Actualización de las acciones de validación de GitHub.
- Intervalo predeterminado de 30 minutos para nuevas instalaciones; los ajustes existentes se conservan.
- Documentación de demoras, límites de solicitudes y desinstalación.

## 0.8.1

- Espera de confirmación de controles ampliada a 180 segundos para respuestas lentas de OnStar.
- Consulta del resultado cada 5 segundos, sin reenviar la orden física.

## 0.8.0

- Primera publicación de la integración para el servidor de OnStar Uruguay.
- Diagnósticos, ubicación, actualización y controles de puertas, luces y bocina.
- Configuración avanzada del cliente móvil validada antes de guardar.
- Icono local y diagnósticos sin credenciales ni datos de vehículo.
