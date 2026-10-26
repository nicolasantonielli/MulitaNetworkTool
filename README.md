# Mulita Network Tool

Aplicacion de diagnostico de red pensada para Raspberry Pi 4, con soporte de entorno de pruebas en Windows.

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
