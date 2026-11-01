"""Verifica las dependencias Qt y la compilación QML sin iniciar servicios de red."""
from pathlib import Path
import os
import sys


def main() -> int:
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    os.environ.setdefault('QT_QUICK_BACKEND', 'software')
    try:
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root))
        # Importar el punto de composición comprueba las dependencias Python
        # sin ejecutar main() ni iniciar capturas o servicios.
        import mulita.bootstrap  # noqa: F401
        from PyQt5 import QtQuick, QtSvg  # noqa: F401
        from PyQt5.QtCore import QUrl
        from PyQt5.QtGui import QGuiApplication
        from PyQt5.QtQml import QQmlComponent, QQmlEngine
        app = QGuiApplication.instance() or QGuiApplication([])
        engine = QQmlEngine()
        qml = root / 'mulita/ui/qt/qml/Main.qml'
        component = QQmlComponent(engine, QUrl.fromLocalFile(str(qml)))
        if component.status() != QQmlComponent.Ready:
            for error in component.errors():
                print(error.toString(), file=sys.stderr)
            raise RuntimeError('No se pudo compilar la interfaz QML.')
    except (ImportError, RuntimeError) as exc:
        print(f'Error de verificación del entorno Qt: {exc}', file=sys.stderr)
        return 1
    print('Verificación del entorno Qt y de los módulos QML completada.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
