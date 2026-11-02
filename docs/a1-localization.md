# Corrección A1: idioma explícito y dominio independiente

**Rama:** `v3.1`  
**Versión:** `3.1.0`

## Objetivo y alcance

Eliminar el estado global de idioma y las traducciones dentro del dominio y de
los servicios, sin modificar las funciones de red. Esta corrección corresponde
a A1 del informe histórico de arquitectura. No constituye una refactorización
de todos los hallazgos del informe.

## Implementación

- `core.messages.Message` representa un código estable y parámetros. No conoce
  catálogos ni traduce al convertirse en texto. Sus parámetros tienen una vista
  de solo lectura.
- Los errores de dominio exponen `code`, `parameters` y el mensaje estructurado.
  La cadena de diagnóstico no consulta el idioma de la interfaz.
- `presentation.i18n.Translator` recibe el idioma explícitamente. Se retiraron
  el selector global `_LANGUAGE` y la función mutante `use()`.
- Los controladores Qt obtienen un traductor a partir de sus propias preferencias.
  Los mensajes estructurados se traducen antes de mostrar o serializar datos para
  QML, incluida la presentación de errores con un idioma explícito.
- `WifiLink.facts()` y `PublicAddress.facts()` devuelven nombres de atributo
  estables. Sus etiquetas se traducen en `presentation.facts`.
- Las etiquetas, agrupaciones y resúmenes visuales TLS se trasladaron desde
  `core.tls` hacia `presentation.tls`.
- `SettingsService` guarda las preferencias antes de actualizar su estado y
  notificar a los suscriptores. No modifica catálogos ni idioma global.
- El adaptador de preferencias convierte las fallas de escritura en un error
  controlado. Si el guardado falla, no se actualiza el idioma ni se notifica un
  cambio exitoso.

## Compatibilidad de exportaciones

Los CSV nuevos utilizan identificadores técnicos estables. Los datos de red y
estados se conservan independientemente del idioma; los archivos anteriores no
se migran ni sobrescriben automáticamente.

Ejemplos:

- Wi-Fi: `ssid`, `address`, `gateway`, `mode`.
- IP pública: `ip`, `version`, `asn`, `organization`.
- Ping: `sequence`, `source`, `ttl`, `time`, `status`.
- TLS: `section`, `test`, `severity`, `result`, `cve`.
- Nmap: `host`, `port`, `protocol`, `port_state`; estados como `open|filtered`.
- Registros de servidores: identificadores de columnas del catálogo de cada servidor.

Los consumidores externos que interpretaban encabezados traducidos deben ajustar
su lectura al esquema de la versión 3.1. Los nombres y las ubicaciones de los
archivos no cambian.

## Verificación

Las pruebas de localización comprueban:

1. Dos instancias con distintos idiomas mantienen catálogos y etiquetas independientes.
2. Una falla de escritura conserva el idioma actual, el archivo persistido y los
   catálogos; la interfaz recibe una notificación de error.
3. Las notificaciones exitosas ocurren después del guardado.
4. Los errores conservan códigos y parámetros anidados, y se traducen al presentarlos.
5. Los valores externos que coinciden con una clave de traducción no se traducen
   accidentalmente; por ejemplo, un SSID llamado `factSsid`.
6. Las exportaciones mantienen el mismo esquema y contenido para ambos idiomas.
7. Los presentadores TLS y los avisos Nmap respetan el traductor explícito.
8. `core` y `services` no importan presentación ni interfaces gráficas.

La verificación ejecutada informó **420 pruebas aprobadas**, distribuidas en
**27 módulos ejecutados en procesos separados**. Esta cifra no representa una
ejecución exitosa de toda la suite Qt dentro de un único proceso: la revisión
anterior registró una interrupción en ese modo que requiere un diagnóstico
independiente.

También se comprobó la compilación Python/QML y el arranque de la aplicación Qt
en un entorno sin pantalla física, con cambios de español a inglés y de regreso.
El arranque muestra advertencias QML de dependencias circulares de geometría ya
observadas anteriormente; no se abordaron en esta corrección.

No se validó hardware físico de Raspberry Pi durante este trabajo.
