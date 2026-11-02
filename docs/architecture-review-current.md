# Revisión actual de cohesión y acoplamiento

Fecha: 2 de noviembre de 2026. Versión: **3.1.1**. Commit revisado: **be15570**.
Esta evaluación complementa el informe histórico `architecture-review.md` y revisa
el estado posterior a A1–A8. No se modificó código de producción ni se ejecutaron
operaciones reales de configuración de red durante esta revisión.

## Conclusión

La arquitectura mejoró de forma sustancial en sus límites explícitos: los datos
ya no dependen de un idioma global, los controladores reciben sus servicios
concretos, las capacidades de plataforma de A3 son sustituibles y las rutas
derivadas tienen una única definición.

Sin embargo, **todavía no puede describirse toda la aplicación como de bajo
acoplamiento y alta cohesión**. La principal debilidad actual es la coordinación
entre tareas, estado de pantalla y almacenamiento. Hay componentes separados
en archivos que siguen dependiendo del orden exacto en que llegan los eventos.
Eso es acoplamiento temporal: una respuesta correcta, pero tardía, puede alterar
una operación nueva.

- **Núcleo de datos y validación:** responsabilidades generalmente claras y
  pruebas útiles. El catálogo de traducciones es grande, pero su tamaño no
  implica falta de cohesión.
- **Adaptadores extraídos:** límites útiles para brillo, paquetes, enlace,
  informes de switch y almacenamiento USB.
- **Controladores:** dependencias explícitas, pero con políticas distintas para
  tareas, sesiones, exportaciones y respuestas atrasadas.
- **Servicios Nmap y servidores:** todavía agrupan responsabilidades con motivos
  diferentes para cambiar.
- **Interfaz QML:** mejor reutilización de IPv4, pero persisten señales demasiado
  amplias y dependencias entre órdenes de navegación.

No recomiendo una reescritura. Recomiendo corregir primero los cinco problemas
reproducidos y después completar las separaciones de responsabilidades.

## Hallazgos comprobados

### R1 — Las tareas de guardado no participan del cierre de la aplicación

**Prioridad alta. Defecto de ciclo de vida reproducido en un proceso aislado.**

Evidencia: `presentation/dispatcher.py:25–39` crea un hilo `daemon` por trabajo
y no devuelve un identificador para esperarlo o cancelarlo.
`services/__init__.py:49` detiene sesiones de red, pero no espera esos trabajos.
`ui/qt/bridge/system.py:48–57` permite reiniciar o apagar desde otro controlador;
`ui/qt/app.py:169` destruye el motor QML sin coordinar las tareas pendientes.

**En lenguaje claro:** guardar dejó de congelar la pantalla, pero la aplicación
puede terminar mientras todavía está escribiendo.

Reproducción: un subproceso ejecutó el despachador real y comenzó a escribir
`STARTEND` con una pausa entre ambas partes. Se comprobó que la primera parte
estaba escrita antes de que terminara el proceso. El proceso salió normalmente
con código 0 y el archivo quedó en `START`.

Esto demuestra el comportamiento de los hilos del despachador al salir; no es
una prueba física de apagado de Raspberry Pi ni implica que cada guardado falle.

**Recomendación:** introducir un dueño del ciclo de vida de las tareas con
registro de trabajos pendientes, cierre ordenado y política explícita de
espera/cancelación. Cierre, reinicio y apagado deben usar ese mismo mecanismo.
Cambiar solamente `daemon=False` no resuelve la entrega tardía de callbacks ni
el orden de destrucción de la interfaz.

**Aceptación:** un guardado demorado no queda interrumpido silenciosamente al
cerrar; la aplicación espera o informa una cancelación controlada antes de
destruir los objetos que recibirían su resultado.

### R2 — Una respuesta atrasada del historial altera una preparación Nmap nueva

**Prioridad alta. Inconsistencia de estado reproducida con un despachador controlado.**

Evidencia: `ui/qt/bridge/nmapscan.py:190` inicia la carga del historial sin
reservar un estado de operación. `start()`, en la línea 155, solo bloquea por
`_running` o `_phase == 'starting'`. `_opened()`, en la línea 307, reemplaza
incondicionalmente resultados y fase cuando termina la lectura anterior.

Reproducción:

1. Se solicita abrir un informe anterior; su respuesta queda pendiente.
2. Se inicia un escaneo y la fase pasa a `starting`.
3. Llega la respuesta anterior y cambia la fase a `ok`.
4. Un segundo `start()` es aceptado aunque la primera preparación siga pendiente.

Quedaron encoladas una lectura y dos preparaciones. No se lanzaron escaneos
reales en esta reproducción.

**Problema arquitectónico:** historial y ejecución comparten variables de estado
sin un contrato de transiciones ni una identidad de operación.

**Recomendación:** separar estado de ejecución y selección de historial, añadir
identificadores de solicitud y descartar resultados obsoletos. Reservar el estado
antes de despachar el trabajo y definir qué operaciones pueden coexistir.

**Aceptación:** cualquier orden de finalización entre abrir historial, iniciar,
cancelar y volver a iniciar conserva una única preparación activa y no reemplaza
los resultados de una operación más reciente.

### R3 — Nmap todavía mezcla persistencia con atención directa de la interfaz

**Prioridad media. Escape de error reproducido; bloqueo potencial identificado por código.**

Evidencia: `ui/qt/bridge/nmapscan.py:56,117,150,205` lee perfiles/historial,
enumera archivos y guarda perfiles directamente desde propiedades o slots Qt.
`services/nmapscan.py:373–378` escribe el JSON de perfiles sin traducir los
errores del sistema de archivos. El controlador captura `MulitaError`.

Reproducción: se simuló `OSError('disk full')` al escribir un perfil usando el
servicio y controlador reales. La excepción salió de `saveProfile()` y no se
emitió ninguna notificación. No se probó que esto cierre la aplicación completa.

Además, las lecturas síncronas se ejecutan en el hilo que atiende QML. Un medio
lento puede bloquearlo; no se realizó una medición de almacenamiento real.

**Recomendación:** extraer repositorios de perfiles e informes, normalizar sus
errores como errores de aplicación y cargar/guardar en segundo plano. Las
propiedades QML deberían devolver una instantánea en memoria, no consultar disco.

**Aceptación:** falla de escritura con notificación controlada y preferencias
anteriores recuperables; lectura demorada sin bloquear el bucle Qt.

A2 quedó corregido para las preferencias generales. Este hallazgo muestra que
esa política todavía no está extendida a la persistencia de perfiles Nmap.

### R4 — Cambiar idioma puede borrar una edición IPv4 pendiente

**Prioridad media. Reproducido con el formulario QML real.**

Evidencia: `ui/qt/bridge/ipv4.py:29` emite `loaded` ante cualquier cambio de
preferencias. `ui/qt/qml/components/IPv4Form.qml:19,131` interpreta esa señal
como una orden de recargar todos los campos desde el modelo.

Reproducción: el controlador tenía `192.0.2.5`; se escribió `192.0.2.99` en el
formulario sin aplicar. Al cambiar el idioma, el campo volvió a `192.0.2.5`.

**Problema arquitectónico:** una misma señal representa dos hechos distintos:
«cambiaron textos de presentación» y «se leyó una configuración de red».
La misma conexión de señales también se activa con otras preferencias.

**Recomendación:** separar las señales de presentación y datos; mantener un
estado de edición local que solo se reemplace tras una carga explícita o una
aplicación confirmada.

**Aceptación:** idioma, tema y escala no alteran campos sin guardar; una lectura
explícita sí actualiza los datos con una política clara sobre cambios pendientes.

### R5 — Una exportación Ping fallida deja un resultado incompleto que bloquea el reintento

**Prioridad media. Reproducido con archivos temporales.**

Evidencia: `services/diagnostics.py:105–134` trata dos archivos como un solo
guardado, pero los escribe secuencialmente. Si falla el segundo, el primero
permanece. El siguiente intento rechaza el nombre porque ya existe.

Reproducción: se forzó una falla al escribir las estadísticas. El primer intento
devolvió `savePingFailed`, quedó `probe.csv` y el reintento devolvió `nameExists`.

**Problema arquitectónico:** la operación de exportación no define qué significa
completar o revertir el conjunto. Cada servicio implementa su propia política de
escritura y errores; pasar la tarea a segundo plano no resuelve esa transacción.

**Recomendación:** encapsular la publicación de resultados, preparar los archivos
en una ubicación temporal y publicar solo el conjunto completo, o revertir las
salidas nuevas si falla la operación. No borrar archivos anteriores del usuario.

**Aceptación:** una falla en cualquier etapa no presenta un conjunto incompleto
como guardado válido y permite reintentar con el mismo nombre.

## Hallazgos de diseño sin defecto funcional reproducido

### R6 — Quedan componentes con responsabilidades demasiado amplias

**Prioridad media de mantenimiento.**

- `services/nmapscan.py` combina preparación/ejecución de procesos, lectura XML,
  perfiles, historial, resolución de archivos y escritura de informes. R2 y R3
  muestran consecuencias concretas de fronteras todavía incompletas.
- `services/servers.py` coordina procesos y registros, pero además prepara
  certificados, usuarios temporales, contraseñas, propietarios de archivos y
  configuración SSH. Por ejemplo, `_sftp()` comienza en la línea 241.
- `core/parsers.py` reúne formatos de red y diagnósticos independientes. Sus
  funciones puras son una fortaleza; la dificultad es reunir muchos motivos
  distintos de cambio en el mismo módulo.
- `core/server_commands.py` separa una familia de comandos, pero depende de
  atributos privados inicializados por `CommandFactory`. La extracción reduce
  tamaño de archivo, no todo el acoplamiento entre clases.

**Recomendación:** priorizar repositorios de Nmap y un preparador SFTP con limpieza
explícita. Dividir analizadores por formato cuando se modifiquen y hacer explícitas
las dependencias de los constructores de comandos. No multiplicar interfaces para
cada llamada pequeña a archivos ni dividir módulos por cantidad de líneas.

### R7 — La navegación de configuración todavía depende de tres órdenes paralelos

**Prioridad baja de mantenimiento.**

Evidencia: `SettingsPage.qml` mantiene `pages` en la línea 10, los elementos del
menú en la 38 y los componentes del `StackLayout` desde la 53. Las tres listas se
relacionan por posición.

Los retornos ya usan nombres y la organización es mucho más clara que antes.
Sin embargo, reordenar una sección todavía exige mantener esas tres posiciones
sincronizadas. No se encontró una página actualmente mal enlazada.

**Recomendación:** un descriptor por página con identificador, etiqueta y
componente, o navegación que seleccione el componente por identificador sin
depender del orden de otra lista.

La corrección A5 es efectiva en separación de páginas y formulario compartido,
pero la afirmación anterior de un único catálogo de orden necesita esta salvedad.

## Fortalezas verificadas

- No se detectaron ciclos en el grafo de importaciones internas explícitas de
  ejecución. Tampoco importaciones de `core` hacia servicios, adaptadores o UI,
  ni de servicios hacia presentación o UI en ese análisis.
- `WifiLink.facts()` y otros modelos utilizan claves estables; el idioma es
  explícito en presentación. Las pruebas de A1 pasan.
- Las preferencias generales guardan antes de publicar y el adaptador normaliza
  sus fallas. Las pruebas de A2 pasan.
- Brillo, recepción de paquetes, lectura del enlace e informes de switch cuentan
  con colaboradores inyectados. Sus pruebas no requieren hardware.
- El controlador IPv4 compartido no contiene operaciones VLAN ni el indicador
  Wi-Fi anterior.
- Los controladores no reciben el contenedor global `Services`.
- `StoragePaths` resuelve las rutas derivadas tanto con construcción directa como
  al reemplazar `capture_dir`; el catálogo se comparte entre consumidores.
- Las exportaciones revisadas utilizan tareas y copias independientes de datos.

Estas fortalezas reducen el acoplamiento estructural. No garantizan por sí solas
el aislamiento del estado, la atomicidad de escrituras o un cierre seguro.

## Verificación y límites

- Inventario y análisis sintáctico de **75 archivos Python de `mulita`**
  (11.882 líneas) y **48 archivos QML** (7.974 líneas).
- Grafo: **244 relaciones de importación internas explícitas de ejecución** y
  12 relaciones adicionales encontradas bajo `TYPE_CHECKING`. No se modelaron
  todas las dependencias dinámicas ni todos los efectos de inicialización de
  paquetes. Las cifras son descriptivas, no una puntuación de calidad.
- Inspección manual centrada en composición, controladores, despachador, sesiones,
  preferencias, IPv4, Nmap, servidores, almacenamiento, exportaciones y QML.
- **441 pruebas aprobadas**, ejecutando cada módulo en un proceso separado.
  No se afirma que toda la suite pase dentro de un único proceso Qt.
- Cinco reproducciones independientes, con colaboradores simulados, archivos
  temporales y un subproceso para verificar la salida de un hilo daemon.
- Verificación de compilación QML aprobada. Los avisos de geometría registrados
  en revisiones anteriores requieren validación visual aparte; no se dedujo
  de ellos un defecto visual específico en esta revisión.
- No se realizó auditoría de seguridad, prueba física de Raspberry Pi, medición
  de rendimiento de almacenamiento ni lectura manual exhaustiva de cada línea.

Las 441 pruebas pasan porque los escenarios reproducidos no están exigidos por
la suite actual. Las reproducciones de esta revisión no se incorporaron como
pruebas permanentes ni se aplicaron correcciones de producción.

## Orden sugerido

1. R1: ciclo de vida de tareas y coordinación con cierre/reinicio.
2. R2: identidad de operaciones y transiciones de estado Nmap.
3. R3: persistencia Nmap y salida controlada de errores.
4. R4: separación de notificaciones de presentación y carga de datos.
5. R5: publicación consistente de exportaciones de varios archivos.
6. R6 y R7: completar separaciones y navegación al intervenir esas áreas.

## Correcciones posteriores

El análisis anterior describe be15570; las correcciones siguientes se verificaron después.

- **R1 · 3.1.2:** Registro de tareas, cierre con espera y reinicio/apagado tras drenar; callbacks tardíos descartados. 43 pruebas relacionadas aprobadas.

- **R2 · 3.1.3:** Se separo la preparacion del estado visual y se invalidaron respuestas antiguas; 32 pruebas aprobadas.

- **R3 · 3.1.4:** Catalogos en memoria y operaciones de perfiles en segundo plano; guardado atomico con error de persistencia. La vista previa valida sintaxis y prepare verifica archivos. 35 pruebas aprobadas.

- **R4 · 3.1.5:** Se separaron notificaciones visuales y carga IPv4; una prueba QML verifica que idioma, tema y escala preservan la edicion y una carga real actualiza el formulario. 30 pruebas aprobadas.

- **R5 · 3.1.6:** Exportacion Ping preparada en temporales y publicada sin sobrescribir, con rollback ante fallos; permite reintento. No garantiza atomicidad conjunta ante corte de energia. 43 pruebas aprobadas.
