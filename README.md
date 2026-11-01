# Mulita Network Tool

Aplicación de diagnóstico de red para Raspberry Pi, con entorno de pruebas en Windows.

## Usuario y rutas de instalación

El instalador detecta el usuario (`SUDO_USER` al usar sudo, o el usuario
actual) y la ubicación real del repositorio. Guarda las rutas en
`/etc/mulita/config.json` y genera el servicio con esas ubicaciones.
El servicio conserva los permisos root necesarios para las herramientas de red;
las rutas de datos no dependen del HOME de root. Las actualizaciones se ejecutan
como el usuario de instalación sobre el repositorio que ejecuta la app.

En una instalación nueva las capturas van a `<home del usuario>/capturas` y el
estado privado (preferencias, certificados y claves) a
`<home del usuario>/.config/mulita`. Las reinstalaciones conservan las rutas ya
guardadas. Si se detectan las carpetas anteriores en el home de root, se siguen
usando: no se mueven ni eliminan datos automáticamente.

Para elegir otras ubicaciones se pueden pasar `--capture-dir /ruta/capturas`
y `--state-dir /ruta/privada` al instalador. Las carpetas
deben ser absolutas y estar separadas para evitar compartir el estado privado.
Elegir otra ubicación no copia los archivos anteriores. Ejemplo para una
pantalla de 7 pulgadas y carpetas personalizadas:

```bash
bash install-lite.sh 7 --capture-dir /home/nico/capturas --state-dir /home/nico/.config/mulita
```

En las secciones siguientes, `<capturas>` representa el valor `capture_dir`
guardado en `/etc/mulita/config.json`; no es una ruta literal. Para consultar
las rutas instaladas:

```bash
cat /etc/mulita/config.json
```

`run.sh` solo inicia la app. Para una configuración alternativa se puede usar
`MULITA_CONFIG=/ruta/config.json bash run.sh`. Si se mueve el repositorio,
volver a ejecutar el instalador actualiza la ruta del servicio.

## Instalación con pantalla de 5 o 7 pulgadas

El archivo anterior `install-lite_7.sh` fue reemplazado por `install-lite.sh`.
Todas las comprobaciones y mejoras se aplican a ambos tamaños de pantalla.
El instalador requiere indicar el panel como parámetro. Ejecutarlo sin `5` o
`7`, o con un valor diferente, termina sin instalar ni modificar el equipo:

- **5 pulgadas, BTT-PITFT50 V1.0:** `bash install-lite.sh 5`
- **7 pulgadas, Waveshare `7_0_inchH` en DSI1:** `bash install-lite.sh 7`

Después de la instalación, ejecutar `sudo reboot`. El instalador prepara las
dependencias de Mulita y el servicio de arranque automático. Para el panel de 7 pulgadas utiliza
`dtoverlay=vc4-kms-v3d` y
`dtoverlay=vc4-kms-dsi-waveshare-panel,7_0_inchH`.
Verifica que existan los overlays, respalda `config.txt` en
`config.txt.mulita-bak` y reemplaza la configuración del panel anterior.
Para 5 pulgadas utiliza `vc4-kms-v3d`,
`vc4-kms-dsi-7inch,disable_touch` y `rpi-ft5406`. El nombre `7inch` del overlay
corresponde al controlador utilizado por ese panel; la selección del instalador
sigue siendo `5`. Para Waveshare, la alternativa DSI0 queda comentada en el
archivo de arranque; la instalación con `7` configura DSI1.

Al cambiar de panel, ejecutar el instalador con el nuevo tamaño y reiniciar.
El instalador reemplaza el bloque del panel anterior y evita activar overlays
incompatibles de ambas pantallas simultáneamente.

El instalador requiere Python 3.10 o posterior y systemd.
Incluye NetworkManager para Ethernet, VLAN y Wi-Fi, verifica el entorno Python,
la compilación de los módulos QML y la unidad de servicio antes de aplicar la
configuración de arranque. El teclado virtual integrado no requiere el plugin
Qt Virtual Keyboard. `testssl.sh` y el controlador DHT11 son opcionales; los
fallos en su instalación se informan explícitamente. El controlador DHT11
heredado se omite en Raspberry Pi 5.

`bash install-lite.sh --help` muestra las opciones admitidas. La instalación
no reinicia el equipo ni inicia la aplicación automáticamente en esa sesión;
el servicio queda habilitado para el próximo arranque. La consola de
recuperación permanece disponible en tty3.

Para iniciar manualmente, usar `bash run.sh`. Este script solo inicia la app;
la instalación y configuración de pantalla se realizan con el parámetro del panel elegido.

## Puerto de switch

El cuadro **Puerto de switch** identifica el vecino conectado mediante anuncios
LLDP y CDP. Seleccionar una interfaz Ethernet y escuchar durante 15 a 180 segundos
(60 por defecto). Muestra nombre del equipo, boca, descripción, dirección de
administración y modelo/descripción del sistema cuando el vecino los anuncia.
Separa PVID/VLAN nativa, VLAN de voz y nombres de VLAN anunciados de las etiquetas
802.1Q observadas en el tráfico recibido. Los anuncios que vencen su TTL o se
retiran dejan de aparecer; LLDP y CDP se conservan como evidencias separadas.

La detección en Linux usa captura Ethernet pasiva con permisos root o
`CAP_NET_RAW`, sin dependencias adicionales, sin necesitar IP y sin cambiar
direcciones, rutas ni configuración del switch. La recepción promiscua dura solo
la sesión y se libera al cerrar el socket. Muestra también enlace, velocidad,
dúplex y contadores de errores locales disponibles en el controlador Ethernet.
**Guardar** exporta un JSON en `<capturas>/puerto-switch/`.

La ausencia de anuncios no demuestra que no haya switch. En una boca de acceso,
los paquetes pueden llegar sin etiqueta y no permiten deducir el número de VLAN.
Las VLAN observadas no enumeran todas las permitidas en un trunk. EDP, medición
eléctrica de PoE, mapa de hilos y certificación de cable no están incluidos.
En Windows y modo test se muestra una demostración marcada **SIMULACIÓN**.

## Menu de inicio

El inicio son pantallas numeradas **1**, **2**, **3**… Cada una lleva de 1 a 6 cuadros,
y un cuadro puede estar en cualquier pantalla. Deslizar cambia de pantalla. Tocar el
numero de abajo tambien la abre. En **Configuración → Interfaz → Orden de cuadros**, **Ordenar** muestra todos los cuadros
juntos, con un separador por pantalla. El **+** del ultimo separador agrega una
pantalla. **Servidores**, **Certificados TLS** y **Escaneo Nmap** ya funcionan. Las
demas herramientas de ciberseguridad usan una plantilla comun y todavia estan en
preparacion.

## Servidores

En el inicio, el cuadro **Servidores** abre la lista de
servicios de prueba. Cada uno tiene dos pestanas: **Ajustes** y **Registro**. El boton
**Iniciar** arranca el servicio y se pueden tener varios activos a la vez, uno por tipo.
El registro guarda las ultimas 500 entradas, con la mas nueva primero, y se puede exportar a
CSV. Un servidor que cae muestra el motivo en un aviso.

| Servicio | Que hace | Puerto por defecto |
| --- | --- | --- |
| iPerf3 | Servidor `iperf3 -s`. El otro equipo corre `iperf3 -c <IP de Mulita>` | 5201 |
| TFTP | Entrega y recibe archivos de la carpeta `servidores/tftp`. Las subidas reemplazan un archivo existente | 69 |
| SFTP | Usuario temporal con clave, limitado a la carpeta de capturas. Las subidas van a `respaldos` | 2222 |
| HTTP/HTTPS | Pagina de conexion, descargas de prueba (`/prueba/10` son 10 MB), `/archivos/` y `/capturas/` | 80 y 443 |
| DNS | Resuelve un nombre de prueba y registra cada consulta. Puede reenviar el resto a otro DNS | 53 |
| DHCP | Reparte direcciones y lista las concesiones | 67 |
| NTP | Entrega la hora del sistema de Mulita | 123 |

Detalles:

- **Interfaz.** iPerf3, TFTP, SFTP, HTTP/HTTPS y NTP escuchan en todas las interfaces o en una
  elegida. DNS y DHCP necesitan una interfaz con direccion IPv4.
- **DHCP.** Se niega a iniciar en la interfaz que tiene la ruta por defecto, para no competir con
  el DHCP de la red. Sin rango, usa la red de la interfaz entre `.100` y `.150`. Gateway y DNS
  valen por defecto la direccion de Mulita.
- **SFTP.** El usuario se crea al iniciar y se elimina al detener. No puede ser un usuario que ya
  exista en el sistema. Solo ve la carpeta de capturas. El registro muestra los ingresos y
  desconexiones, no cada archivo. El puerto 22 queda para el SSH del sistema.
- **HTTPS.** Usa un certificado propio, creado la primera vez. El navegador avisa que no es
  confiable. El certificado y las claves se guardan fuera de las carpetas compartidas.
- **DNS.** Responde el nombre de prueba (`mulita.test` por defecto) con la direccion elegida y
  no guarda respuestas en memoria, asi el registro muestra todo lo que pregunta el equipo.
- **NTP.** La precision es la del reloj de Mulita. El estrato anunciado se elige a mano.
- Los puertos menores a 1024 funcionan porque Mulita corre como administrador.
- Los archivos estan en `<capturas>/servidores`: `tftp` (TFTP), `web` (servidor web) y
  `registros` (CSV del registro).

Necesitan `iperf3`, `dnsmasq-base`, `openssh-server` y `openssl`, que instala `install-lite.sh`.

## Certificados TLS

El cuadro **Certificados TLS** de Ciberseguridad analiza un servidor con
[testssl.sh](https://testssl.sh). Tiene tres pestanas: **Analisis**, **Resultado** y **Salida**.

1. En **Analisis**, escribir el servidor (`ejemplo.com`, `ejemplo.com:8443`, una IP o una URL
   `https://...`; sin puerto usa el 443) y elegir el tipo de analisis.
2. **Iniciar** pasa a **Salida**, donde se ve el avance de testssl.sh. **Detener** corta el
   analisis y deja lo que alcanzo a revisar.
3. Al terminar se abre **Resultado**: un resumen por severidad y una tabla agrupada en
   Certificado, Protocolos, Cifrados, Vulnerabilidades y Otros. Mantener presionada una celda
   permite copiar su texto.

| Tipo | Que revisa | Demora |
| --- | --- | --- |
| Certificado | Nombre, emisor, vigencia, firma, tamano de clave, cadena de confianza y OCSP | segundos |
| Protocolos y cifrados | Versiones SSL/TLS ofrecidas y categorias de cifrados | un minuto o dos |
| Vulnerabilidades | Heartbleed, ROBOT, SWEET32, POODLE, renegociacion y otras | un minuto o dos |
| Completo | Los tres anteriores | varios minutos en la Pi |

- **Guardar** crea un CSV en `<capturas>/tls` llamado `tls-<servidor>-<fecha>-<hora>.csv`. Aparece
  en el gestor de archivos de Herramientas como **Certificados TLS**.
- Se prueba una sola direccion, aunque el nombre tenga varias. Un servidor con mas de un
  certificado (RSA y ECDSA) muestra cada uno con su numero, por ejemplo `#2`.
- Los resultados dependen de que Mulita llegue al servidor por la red. Para probar el HTTPS de la
  propia Mulita, usar su direccion y el puerto 443.
- Necesita el paquete `testssl.sh`. `install-lite.sh` lo instala, pero sin detener la instalacion
  si no esta en los repositorios. En ese caso la aplicacion avisa que falta.

## Escaneo Nmap

El cuadro **Escaneo Nmap** reemplaza al marcador de DHCP falso. No es una terminal: se elige un
perfil, se ve el comando completo y Nmap corre como proceso directo, sin shell.

Hay perfiles para descubrimiento, ARP local, TCP (rápido, estándar, todos los puertos y SYN),
puertos a elección, versiones, sistema operativo, UDP, certificados y cifrados TLS, SMB, SSH,
HTTP y comprobaciones sueltas. El modo **Comando propio** acepta argumentos o un comando pegado
que empiece por `nmap` (se quita solo ese nombre). Se puede guardar, duplicar y borrar.

- Un escaneo a la vez. **Detener** corta también los procesos hijos y marca el informe como
  cancelado. Si el XML quedó a medias, la lectura se señala como parcial.
- El estado `open|filtered` se muestra como «Abierto o filtrado». Una versión detectada no se
  presenta como vulnerabilidad, y la falta de hallazgos no se presenta como seguridad.
- Cada ejecución queda en `<capturas>/nmap/<fecha>/`: `informe.xml`, `salida.txt`,
  `progreso.txt`, `errores.txt`, `puertos.csv` y `meta.json`. El historial abre, reutiliza y
  compara dos escaneos.
- En Windows, o con `--test`, la pantalla muestra **Simulación**. No inventa resultados.
- Nmap ya lo instala `install-lite.sh`.

## Copiar y pegar texto

Mantener presionado un texto para abrir el menu **Copiar**. Vale para un texto
informativo, un resultado o una celda. Seleccionar texto con el cursor y soltar
abre el mismo menu para esa seleccion. El clic derecho tambien permite abrirlo. El portapapeles
solo se modifica al elegir **Copiar**; tocar fuera o presionar Escape cierra el
menu sin copiar. En cuadros editables, incluso vacios, el menu tambien ofrece
**Pegar**: inserta el portapapeles en el cursor o reemplaza la seleccion. Tocar
fuera cierra el menu sin modificar el campo. Pegar queda deshabilitado cuando
el portapapeles no contiene texto. El arrastre vertical conserva el desplazamiento
de las tablas.

## Prueba del panel tactil

En **Configuracion > Pantalla > Test tactil**:

- Tocar las nueve zonas y dibujar lineas para comprobar posiciones y continuidad.
- Repetir cinco toques en un mismo punto y comparar el contador de la zona con el boton de prueba.
- Los trazos verdes representan eventos tactiles recibidos por Qt; los azules, eventos de mouse o sintetizados por Qt.
- Los contadores de la ventana muestran pulsaciones (flecha abajo), liberaciones (flecha arriba) y cancelaciones (cruz). Incluyen los controles del test. No sumar panel y Mouse/Qt: un mismo toque puede producir ambos tipos de evento.
- El control **Modo normal / Sin correccion** permite comparar el filtro de Mulita con la entrada que recibe Qt. Al salir se restaura automaticamente el modo normal.
- **Detener** finaliza la prueba y vuelve a **Configuración → Pantalla**.
- **Limpiar** borra los contadores, las marcas y el historial. Se conservan como maximo los ultimos 200 registros durante la prueba.

La prueba observa lo que Qt recibe, no los eventos crudos del kernel. Que no aparezcan eventos verdes no demuestra por si solo una falla del panel: algunos sistemas entregan solamente eventos de mouse.

## Requisitos

- Python 3.10 o superior.
- En Raspberry Pi (Debian/Raspberry OS), acceso a `apt` para instalar dependencias del sistema.

## Instalar, actualizar e iniciar en Raspberry Pi

Ejecutar los comandos desde la carpeta que contiene `main.py` e `install-lite.sh`,
con el usuario propietario del repositorio. El instalador solicita `sudo` cuando
necesita permisos administrativos; también admite ejecutarse con `sudo` y
conserva la identidad del usuario original mediante `SUDO_USER`.

Para una pantalla de 5 pulgadas:

```bash
git pull origin v3
bash install-lite.sh 5
sudo reboot
```

Para una pantalla Waveshare de 7 pulgadas conectada a DSI1:

```bash
git pull origin v3
bash install-lite.sh 7
sudo reboot
```

La instalación prepara dependencias, entorno virtual, rutas, pantalla y servicio.
Debe repetirse cuando una actualización modifica esos componentes o cuando se
cambia el panel. Para una actualización que solo modifica la aplicación basta
actualizar el repositorio y reiniciar el servicio:

```bash
git pull origin v3
sudo systemctl restart mulita
```

`run.sh` únicamente inicia la aplicación con el entorno virtual existente. No
instala paquetes ni modifica las rutas, el servicio o la pantalla. Si el servicio
ya está ejecutándose, detenerlo antes de iniciar otra instancia manual:

```bash
sudo systemctl stop mulita
sudo bash run.sh
```

El uso de `sudo` permite utilizar las funciones que requieren acceso de
administrador, como capturas, configuración de red y servicios en puertos bajos.
Para una ejecución manual en simulación sin privilegios:

```bash
bash run.sh --test
```

Otras opciones:

- Interfaz Tk heredada: `bash run.sh --tk`.
- Desactivar el teclado integrado: `bash run.sh --no-keyboard`.
- Ayuda del instalador: `bash install-lite.sh --help`.

Para volver al servicio automático después de cerrar la instancia manual:

```bash
sudo systemctl start mulita
```

Si la aplicación no aparece, consultar el estado y el registro antes de repetir
la instalación:

```bash
sudo systemctl status mulita --no-pager -l
sudo journalctl -u mulita -b -n 100 --no-pager
```

El instalador verifica la unidad con `systemd-analyze verify`. El registro
permite distinguir fallos del servicio, dependencias o salida de pantalla.

## Configuración de la interfaz y la pantalla

- **Configuración → Interfaz:** orden de cuadros, tema claro/oscuro y switch
  para habilitar el redimensionamiento de los cuadros.
- **Configuración → Pantalla:** escala, brillo, prueba táctil y orientación
  de **0°, 90°, 180° o 270°**. La orientación se aplica a la interfaz, los
  controles táctiles, los diálogos y el teclado, y se guarda sin reinstalar.

## Ejecutar entorno de test en Windows

Se incluyen scripts para trabajar en Windows sin hardware de Raspberry:

- `run_windows_test.ps1`
- `run_windows_test.bat`

La forma recomendada es usar el `.bat`:

```bat
run_windows_test.bat
```

Este comando (sin opciones) inicia la UI final en Qt Quick:

1. Crea (si no existe) el entorno virtual en `%LOCALAPPDATA%\Mulita\venv-win`.
2. Instala dependencias de `requirements.txt`.
3. Ejecuta tests del proyecto.
4. Inicia la aplicacion en modo simulacion (`MULITA_TEST=1`) con Qt Quick y `--no-keyboard`.

El modo por defecto en Windows ya usa Qt Quick, instala `PyQt5` en ese entorno y arranca sin `--tk`.

### Comandos frecuentes en Windows

- Solo preparar entorno (sin tests ni UI):

```bat
run_windows_test.bat -NoUi -SkipTests
```

- Rehacer el entorno virtual desde cero:

```bat
run_windows_test.bat -RecreateVenv
```

- Ejecutar sin tests pero iniciar la app:

```bat
run_windows_test.bat -SkipTests
```

- Ejecutar UI Qt Quick sin tests:

```bat
run_windows_test.bat -SkipTests
```

- Forzar interfaz Tk legada (solo para fallback):

```bat
run_windows_test.bat -TkLegacy
```

Si tu politica de PowerShell bloquea scripts:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_windows_test.ps1
```
