# Mulita Network Tool

Aplicacion de diagnostico de red pensada para Raspberry Pi 4, con soporte de entorno de pruebas en Windows.

## Menu de inicio

El inicio tiene dos paginas de seis cuadros: **Red** y **Ciberseguridad**.
Deslizar el dedo hacia la izquierda pasa a Ciberseguridad y hacia la derecha
vuelve a Red. Tocar el nombre de una pagina, debajo de los cuadros, tambien la
abre. Las herramientas de Ciberseguridad usan una plantilla comun y todavia
estan en preparacion.

## Servidores

En la pagina **Ciberseguridad** del inicio, el cuadro **Servidores** abre la lista de
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
- Los archivos estan en `/root/capturas/servidores`: `tftp` (TFTP), `web` (servidor web) y
  `registros` (CSV del registro).

Necesitan `iperf3`, `dnsmasq-base`, `openssh-server` y `openssl`, que instala `install-lite.sh`.

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
- **Limpiar** borra los contadores, las marcas y el historial. Se conservan como maximo los ultimos 200 registros durante la prueba.

La prueba observa lo que Qt recibe, no los eventos crudos del kernel. Que no aparezcan eventos verdes no demuestra por si solo una falla del panel: algunos sistemas entregan solamente eventos de mouse.

## Requisitos

- Python 3.10 o superior.
- En Raspberry Pi (Debian/Raspberry OS), acceso a `apt` para instalar dependencias del sistema.

## Ejecutar en Raspberry Pi

El instalador esta configurado para la pantalla **BTT-PITFT50 V1.0** en Raspberry Pi 4.
En `config.txt` desactiva la deteccion automatica de pantalla, configura el video
con `vc4-kms-dsi-7inch,disable_touch` y habilita el tactil por firmware con
`rpi-ft5406` y `disable_touchscreen=0`. Esta es la configuracion probada en el equipo
para evitar los contactos fantasma del acceso directo mediante `edt_ft5x06`.

El script usa `/boot/firmware/config.txt` o `/boot/config.txt` segun el sistema,
conserva la primera copia en `config.txt.mulita-bak` y permite repetir la instalacion
sin duplicar los ajustes. Comprueba que los overlays esten instalados y conserva
los demas ajustes de arranque. Los cambios se aplican al reiniciar.

Para actualizar la configuracion de un equipo ya instalado:

```bash
git pull origin v3
bash install-lite.sh
sudo reboot
```

El script principal para Raspberry instala dependencias del sistema, prepara el entorno virtual y arranca la app:

```bash
bash run.sh
```

Opciones utiles:

- Interfaz Tk (legada): `bash run.sh --tk`
- Modo test/simulacion: `bash run.sh --test`

## Ejecutar entorno de test en Windows

Se incluyen scripts para trabajar en Windows sin hardware de Raspberry:

- `run_windows_test.ps1`
- `run_windows_test.bat`

La forma recomendada es usar el `.bat`:

```bat
run_windows_test.bat
```

Este comando (sin opciones) inicia la UI final en Qt Quick:

1. Crea (si no existe) el entorno virtual `.venv-win`.
2. Instala dependencias de `requirements.txt`.
3. Ejecuta tests del proyecto.
4. Inicia la aplicacion en modo simulacion (`MULITA_TEST=1`) con Qt Quick y `--no-keyboard`.

El modo por defecto en Windows ya usa Qt Quick, instala `PyQt5` en `.venv-win` y arranca sin `--tk`.

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
