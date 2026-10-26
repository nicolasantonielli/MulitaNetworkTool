"""Una aplicacion Qt sin ventanas visibles, compartida por las pruebas."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')

from PyQt5.QtGui import QGuiApplication


def qt_app():
    return QGuiApplication.instance() or QGuiApplication([])
