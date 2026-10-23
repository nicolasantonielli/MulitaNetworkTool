# Mulita Network Tool

Aplicacion de diagnostico de red pensada para Raspberry Pi 4, con soporte de entorno de pruebas en Windows.

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
