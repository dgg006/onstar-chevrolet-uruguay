# Privacidad y seguridad

Las credenciales de cada cuenta se configuran únicamente en su instancia de Home Assistant. No incluir contraseñas, PIN, tokens, VIN, coordenadas, capturas HAR, APK ni copias de configuración en incidencias o contribuciones.

La distribución incluye únicamente la configuración compartida del cliente móvil identificada en el APK. Esa clave de aplicación no es una contraseña de usuario ni un token de acceso a un vehículo. No permite por sí sola acceder a una cuenta. Se utiliza junto con las credenciales personales en el acceso a GM. No se ha confirmado una autorización de redistribución específica de GM.

Las modificaciones hechas desde la interfaz se guardan en la configuración de Home Assistant. Los campos de clave no se devuelven como valores predeterminados del formulario. Los diagnósticos de la integración omiten correo, contraseña, PIN, claves, tokens, VIN y ubicación. Las copias de seguridad de Home Assistant pueden contener credenciales personales y deben mantenerse privadas.

La integración usa HTTPS con validación de certificados y no registra cuerpos de respuesta ni valores de autenticación. Los ejemplos y pruebas usan datos ficticios.

Para reportar un problema, incluir la versión de la integración y de Home Assistant, el país y el mensaje de error, omitiendo información de la cuenta o del vehículo. Si se publica una credencial personal accidentalmente, retirarla y reemplazarla en el servicio correspondiente.
