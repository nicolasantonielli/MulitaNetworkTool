# Revisión de arquitectura

**Revisión del repositorio analizada:** `3e3370d`  
**Fecha de revisión:** 1 de noviembre de 2026  
**Alcance:** arquitectura de la aplicación, acoplamiento, cohesión, dirección de dependencias y verificación automatizada.

## Conclusión

La aplicación tiene una base útil organizada por capas, pero **no mantiene de forma consistente un bajo acoplamiento ni una alta cohesión**. El punto central de composición, la ejecución de comandos mediante una dependencia inyectada, los modelos de datos simples y las interfaces Qt y Tk separadas permiten mejorarla de manera incremental. Sin embargo, el estado global de idioma, la infraestructura concreta dentro de los servicios, las dependencias amplias de los controladores y la mezcla de responsabilidades de interfaz debilitan esos límites.

Esta revisión no recomienda una reescritura completa. Los cambios de mayor valor son independizar los resultados del dominio respecto de la presentación, completar la inyección de dependencias en el límite de la aplicación y extraer componentes de interfaz cohesivos. La longitud de un archivo, por sí sola, no se considera un defecto.

No se modificó código de producción durante esta revisión.

## Método y cobertura

- El análisis sintáctico de Python y de las importaciones internas abarcó los 82 archivos Python de `mulita` —12.525 líneas—.
- El inventario QML abarcó los 41 archivos QML —8.026 líneas—. La inspección manual se concentró en la estructura principal de la aplicación, la configuración, la navegación de inicio y los controles reutilizables.
- También se examinaron el punto de entrada, los cuatro scripts auxiliares de instalación en Python, ambos scripts de shell, la composición de servicios, los adaptadores, la integración Qt/Tk y la organización de las pruebas.
- Se siguieron recorridos representativos desde una acción de interfaz hasta el servicio, la construcción del comando, el adaptador, la función de respuesta y la exportación.
- Se intentó ejecutar la suite completa por descubrimiento y se ejecutaron por separado los 26 módulos de pruebas.
- Se realizaron reproducciones pequeñas en memoria para comprobar el aislamiento del idioma, los errores de escritura de configuración y la derivación de rutas de almacenamiento.

El análisis de importaciones no detectó ciclos internos ni importaciones desde servicios hacia la interfaz. Es una señal positiva sobre la dirección de las dependencias; no demuestra independencia de comportamiento ni elimina el acoplamiento durante la ejecución mediante estado compartido.

No se realizó una lectura manual exhaustiva de cada línea, una auditoría de seguridad o licencias, ni una validación física en Raspberry Pi.

## Hallazgos

### A1. Los resultados del dominio dependen de un estado global de presentación

**Prioridad:** alta desde el punto de vista arquitectónico; inconsistencia de comportamiento reproducida.

**Evidencias:**

- [`mulita/core/models.py:6`](../mulita/core/models.py) importa `presentation.i18n.tr`. `WifiLink.facts()`, en la línea 112, y `PublicAddress.facts()`, en la línea 308, generan campos traducidos.
- La validación, los analizadores y las reglas de configuración, Nmap y TLS también importan el módulo de traducción de presentación.
- [`mulita/services/settings.py:32`](../mulita/services/settings.py) cambia el idioma global del proceso durante su construcción. `_commit()`, en la línea 80, lo cambia antes de guardar la configuración.
- [`mulita/services/wifi.py:40`](../mulita/services/wifi.py) serializa a CSV los campos traducidos por `facts()`.

**Efecto observado:** crear un servicio de configuración en inglés cambia la etiqueta de campo producida por un modelo utilizado previamente por un servicio en español, aunque el primer servicio siga informando español. El mismo `WifiLink(ssid='Office')` pasa de `('Red', 'Office')` a `('Network', 'Office')`.

Una falla de almacenamiento simulada durante `set_language('en')` también deja `current.language` en español mientras la etiqueta global del modelo pasa a inglés. No se trata solamente de una preferencia sobre la organización de carpetas: el estado compartido de presentación puede quedar en desacuerdo con el estado persistido de la aplicación.

**Recomendación:** devolver identificadores estables de campos y errores estructurados desde el dominio. Traducir en presentadores o adaptadores de interfaz con un idioma explícito. Definir si las exportaciones son un formato estable para procesamiento automático o un informe localizado, en lugar de heredar implícitamente el idioma global. Publicar los cambios de idioma únicamente después de guardar correctamente.

**Criterios de aceptación:** dos instancias configuradas de manera independiente no alteran sus resultados entre sí; una falla de persistencia no cambia el idioma activo; los módulos del dominio no importan módulos de presentación.

### A2. Los errores de almacenamiento atraviesan el límite de la aplicación sin normalizarse

**Prioridad:** alta para la confiabilidad.

**Evidencias:** [`JsonSettingsStore.save()`](../mulita/adapters/settings_store.py), en la línea 28, crea directorios, escribe archivos y los reemplaza sin traducir los errores del sistema de archivos. [`SettingsController.setLanguage()`](../mulita/ui/qt/bridge/system.py), en la línea 120, captura `MulitaError`, mientras las operaciones de almacenamiento pueden lanzar `OSError`.

**Impacto:** una falla habitual de infraestructura, como un directorio de solo lectura o falta de espacio, puede quedar fuera del manejo de errores previsto por la interfaz. El controlador necesita conocer implícitamente excepciones específicas de la implementación para cubrir todas las fallas.

**Recomendación:** definir un error de persistencia dentro de la jerarquía de errores de aplicación o dominio y traducir las excepciones del sistema de archivos en el adaptador. Conservar los detalles de bajo nivel en la excepción encadenada o en los registros, y presentar un error consistente a la interfaz.

**Criterios de aceptación:** un almacén de configuración inyectado que falla produce una notificación controlada; las preferencias y el estado de presentación permanecen consistentes después del error.

### A3. Algunos servicios todavía construyen u operan infraestructura directamente

**Prioridad:** media desde el punto de vista arquitectónico.

**Evidencias:**

- [`mulita/services/settings.py:30`](../mulita/services/settings.py) construye `PanelBacklight()` si no se proporciona la dependencia, aunque ya declara un protocolo `Backlight`.
- [`mulita/services/switchport.py:66`](../mulita/services/switchport.py) abre directamente un socket `AF_PACKET`. El mismo servicio lee datos del enlace desde sysfs, mantiene el estado de descubrimiento, genera datos simulados y escribe informes JSON.
- [`mulita/services/files.py`](../mulita/services/files.py) combina operaciones sobre capturas, metadatos orientados a presentación, descubrimiento USB, inspección de sysfs/procfs y coordinación de montajes.

**Impacto:** el punto de composición no es el único lugar que selecciona implementaciones de plataforma. Las pruebas y las plataformas alternativas deben sustituir objetos globales de módulos o depender de comprobaciones de plataforma, en vez de reemplazar capacidades específicas.

**Recomendación:** inyectar el contrato de brillo existente desde `bootstrap`. Introducir interfaces específicas de recepción de paquetes, lectura del enlace y almacenamiento extraíble donde se necesite sustituirlas. Separar la agregación de información de protocolos del manejo de sockets y la persistencia de informes. Evitar una abstracción genérica del sistema de archivos para cada operación pequeña.

**Criterios de aceptación:** el comportamiento del servicio puede probarse con colaboradores proporcionados, sin abrir interfaces de hardware ni sustituir globalmente `socket.socket`.

### A4. Un controlador de Ethernet también implementa Wi-Fi mediante un indicador

**Prioridad:** media desde el punto de vista arquitectónico.

**Evidencias:** [`InternalEthernetController.__init__()`](../mulita/ui/qt/bridge/ethernet.py), en la línea 23, acepta `wifi=False`. Este indicador selecciona servicios, cambia nombres y notificaciones, modifica la actualización de datos y suprime operaciones VLAN. [`mulita/ui/qt/app.py`](../mulita/ui/qt/app.py) registra la misma clase como `interna` y `wifiIp`.

**Impacto:** el tipo expone acciones específicas de Ethernet a la instancia Wi-Fi y depende de condicionales en lugar de un contrato común declarado. Agregar otro tipo de conexión requeriría más bifurcaciones dentro del mismo controlador.

**Recomendación:** introducir un contrato compartido para configurar IPv4 —`read`, `apply_dhcp` y `apply_static`— y un presentador o controlador IPv4 cohesivo. Mantener la gestión VLAN en un controlador o colaborador específico de Ethernet. Inyectar la implementación y los datos de presentación en lugar de seleccionarlos mediante un indicador del tipo de conexión.

**Criterios de aceptación:** el controlador IPv4 compartido no tiene condicionales `wifi` ni operaciones VLAN; Ethernet y Wi-Fi pueden probarse independientemente.

### A5. La configuración QML mezcla funciones independientes y duplica formularios IPv4

**Prioridad:** media para la mantenibilidad.

**Evidencias:** [`SettingsPage.qml`](../mulita/ui/qt/qml/pages/SettingsPage.qml) tiene 972 líneas. Contiene configuración general, pantalla, descubrimiento Wi-Fi, ingreso de contraseñas, perfiles guardados, dos formularios IPv4, VLAN, mantenimiento, navegación del test táctil y orden de cuadros. La sección IPv4 de Wi-Fi comienza alrededor de la línea 334 y Ethernet alrededor de la 688. La navegación depende de índices numéricos, incluidas las comprobaciones de las líneas 25–28 y los destinos de retorno de las líneas 968–969.

Las dos implementaciones de `showStatic()` también difieren: el formulario Wi-Fi limpia los valores opcionales de puerta de enlace y DNS, mientras el formulario Ethernet solo los asigna si no están vacíos. Esto demuestra cómo dos implementaciones paralelas pueden divergir.

**Recomendación:** extraer páginas de configuración por función y un formulario IPv4 compartido. Reemplazar el conocimiento disperso de índices por constantes de navegación con nombre o identificadores estables de página. Mantener la coordinación en la página principal de configuración y el estado de los campos en su componente correspondiente.

**Criterios de aceptación:** un único formulario IPv4 define cómo cargar y limpiar campos; agregar o reordenar una sección no exige modificar índices de retorno de otras funciones.

### A6. Las exportaciones no utilizan consistentemente el mecanismo de ejecución asíncrona

**Prioridad:** media para la capacidad de respuesta de la interfaz.

**Evidencias:** [`WifiController.saveLink()`](../mulita/ui/qt/bridge/wifi.py), en la línea 106, llama directamente a `WifiService.save()` desde un slot Qt. [`mulita/services/wifi.py:60`](../mulita/services/wifi.py) ejecuta `os.sync()` después de escribir. Otros controladores también guardan directamente, mientras las búsquedas y conexiones utilizan `TaskController._task()`.

**Impacto:** exportar datos puede ejecutar operaciones de archivos y una sincronización global del sistema desde el hilo gráfico. Un almacenamiento lento puede bloquear la navegación y los toques, aunque el proyecto ya dispone de ejecución en segundo plano.

**Recomendación:** ejecutar las exportaciones potencialmente bloqueantes mediante el mecanismo de tareas existente, utilizar instantáneas inmutables de los datos y notificar la finalización a través del despachador. Revisar si cada exportación necesita una sincronización global o si una operación de durabilidad más acotada satisface el requisito.

**Criterios de aceptación:** un exportador simulado con demora no bloquea el hilo gráfico y las solicitudes duplicadas de guardado se manejan consistentemente.

### A7. Los controladores reciben un contenedor global de servicios en lugar de sus dependencias concretas

**Prioridad:** media desde el punto de vista arquitectónico.

**Evidencias:** [`BridgeContext`](../mulita/ui/qt/bridge/base.py), en la línea 46, contiene el contenedor completo `Services`. `Controller`, en la línea 53, lo copia a cada controlador. [`Services`](../mulita/services/__init__.py) referencia implementaciones concretas de todas las funciones. Tk utiliza un `ScreenContext` igualmente amplio.

**Impacto:** las firmas de los constructores no expresan qué necesita cada controlador. Todos pueden acceder a todos los servicios y las dependencias de importación abarcan más que las de cada función. El patrón admite pruebas con objetos simulados, pero debilita la aplicación efectiva de los límites entre funciones.

**Recomendación:** conservar la construcción centralizada en `bootstrap` o en la fábrica de interfaz y proporcionar a los controladores protocolos específicos o pequeños grupos de dependencias. Aplicar el cambio gradualmente a los controladores extraídos, sin reemplazar todo el contexto de la aplicación de una vez.

**Criterios de aceptación:** una prueba del controlador Wi-Fi proporciona Wi-Fi, idioma, notificaciones y tareas sin exponer servidores, capturas o mantenimiento.

### A8. Las utilidades compartidas y las rutas tienen varias fuentes de verdad

**Prioridad:** baja desde el punto de vista arquitectónico; se confirmó un defecto de portabilidad en una prueba.

**Evidencias:**

- [`CommandFactory`](../mulita/core/commands.py) construye comandos de red, capturas, servidores, USB, cuentas de usuario, teclado, actualización y apagado. Su módulo también resuelve la ubicación de los programas de servidor incluidos en el despliegue.
- [`mulita/core/parsers.py`](../mulita/core/parsers.py) combina formatos externos independientes en 857 líneas. Sus funciones son generalmente puras; el problema son los distintos motivos para cambiar el módulo, no su tamaño por sí solo.
- [`AppConfig`](../mulita/config.py), alrededor de las líneas 81–98, declara rutas de captura independientes; `_installation_paths()`, en la línea 123, vuelve a derivar esos directorios. Los constructores de servicios agregan otros valores predeterminados.
- Los catálogos de ubicaciones de archivos aparecen por separado en el servicio de archivos, Nmap y el código que alimenta QML.

**Efecto observado:** crear directamente `AppConfig(capture_dir=custom_path)` deja `wifi_dir` en su valor predeterminado independiente. El cargador JSON de la instalación actualmente establece ambos, por lo que se trata de una inconsistencia del constructor o contrato de configuración, no de evidencia de una falla de las rutas en una instalación normal.

**Recomendación:** agrupar constructores de comandos y analizadores por función al modificarlos, mover los detalles de despliegue hacia adaptadores y derivar las rutas desde un único objeto `StoragePaths`. Centralizar los identificadores de almacenamiento compartidos y mantener explícitas las reglas de filtrado particulares de cada consumidor.

**Criterios de aceptación:** cambiar la carpeta de capturas por un mecanismo de configuración admitido actualiza todos los directorios derivados; las pruebas utilizan rutas temporales explícitas en lugar del directorio personal del usuario que las ejecuta.

## Fortalezas arquitectónicas existentes

- `bootstrap.build_services()` centraliza la mayor parte de la construcción y la inyección de dependencias.
- `CommandRunner`, `RunningCommand`, `SettingsStore` y `ClimateSensor` ofrecen límites útiles para sustituir implementaciones.
- Los comandos se expresan principalmente como listas de argumentos y se ejecutan mediante un adaptador, no como cadenas de shell concatenadas.
- Los módulos del núcleo no importan Qt ni Tk y los servicios no importan ninguna de las dos interfaces.
- Muchos modelos son clases de datos inmutables y la validación y el análisis de formatos tienen pruebas considerables.
- `ProcessSession`, `TaskController` y el despachador ofrecen mecanismos reutilizables de ciclo de vida y ejecución en hilos.
- Las preferencias se guardan mediante reemplazo de archivos; los configuradores de pantalla conservan respaldos y admiten ejecuciones repetidas.
- Los módulos específicos de dominio, como el análisis de tramas de switch, TLS y Nmap, son unidades cohesivas útiles aunque sus implementaciones sean extensas.

La cantidad elevada de importaciones en el punto de composición es esperable y no constituye por sí sola un defecto de acoplamiento.

## Resultados de verificación y limitaciones

### Pruebas automatizadas

La ejecución por descubrimiento en un único proceso terminó con código de salida 1 y sin un resumen final de unittest. La última prueba registrada fue `test_hold_on_action_button_does_not_open_copy_menu`, de `test_table_copy`. Esto no establece la causa de la interrupción.

Posteriormente, los 26 módulos de pruebas se ejecutaron en procesos Python separados:

- **409 pruebas informadas.**
- **408 aprobadas y 1 fallida.**
- `test_table_copy` pasó por separado. El ciclo de vida compartido de Qt o el orden de ejecución siguen siendo causas posibles de la interrupción conjunta, no un diagnóstico confirmado.

La falla aislada corresponde a [`tests/test_tap_output.py:25`](../tests/test_tap_output.py): la prueba entrega `/root/capturas/tap/sesion.pcap` y construye un `AppConfig()` predeterminado cuya carpeta de capturas ahora depende del directorio personal del usuario. `TapController._output()` elimina la ruta configurada, no cualquier directorio anterior. Los datos de preparación de la prueba deben configurar una carpeta explícita o construir la entrada a partir de esa configuración. Esta falla evidencia una suposición de entorno desactualizada en la prueba, no demuestra que la captura TAP en producción esté rota.

### Reproducciones

- Construir un segundo servicio de configuración cambió las etiquetas de los modelos del primero sin cambiar su idioma configurado.
- Una escritura de preferencias fallida simulada cambió los textos globales mientras el idioma almacenado y actual permanecía sin cambios.
- Modificar únicamente `AppConfig.capture_dir` no actualizó el directorio Wi-Fi, que tiene un valor predeterminado independiente.

### Límites de la revisión

- No se probaron físicamente la pantalla, el adaptador Wi-Fi, las VLAN, la captura del switch, el sensor GPIO ni el arranque de Raspberry Pi.
- No se agregaron al repositorio nuevas pruebas para exigir reglas arquitectónicas.
- El análisis de importaciones incluye las declaradas estáticamente, también dentro de funciones. El acceso dinámico a atributos y los comportamientos de plataforma requieren verificación adicional.
- Las métricas de código describen únicamente esta revisión; no constituyen una puntuación de calidad ni demuestran cobertura completa de pruebas.

## Secuencia de refactorización recomendada

1. **Estabilizar la configuración:** normalizar errores de almacenamiento y eliminar la mutación global de idioma anterior al guardado. Incorporar pruebas de falla y aislamiento de idiomas.
2. **Precisar contratos y construcción:** inyectar la implementación de brillo y definir contratos pequeños de IPv4 y de acceso al sistema donde se necesite sustituir implementaciones.
3. **Separar controladores y vistas:** extraer el presentador y formulario IPv4 compartidos, el comportamiento VLAN y las páginas independientes de configuración. Reemplazar el conocimiento disperso de índices de navegación.
4. **Uniformar las tareas:** trasladar las exportaciones bloqueantes al despachador existente y agregar pruebas de capacidad de respuesta.
5. **Unificar configuración y catálogos:** derivar las rutas una sola vez, actualizar los datos de preparación de TAP y probar rutas personalizadas.
6. **Mantener las reglas en verificación continua:** agregar comprobaciones de dirección de importaciones, diagnosticar la interrupción de la suite Qt completa y dividir utilidades amplias cuando se modifiquen sus funciones.

El resultado esperado es una secuencia de cambios pequeños y revisables que conserven el comportamiento, en lugar de un rediseño simultáneo de todos los módulos.
