"""Protect the dependency direction, including nested and relative imports."""
import ast
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest


class LayerDependenciesTest(unittest.TestCase):
    def test_application_layers_do_not_import_their_outer_implementations(self):
        root = Path(__file__).resolve().parents[1]
        rules = {
            'core': ('mulita.adapters', 'mulita.services', 'mulita.servers', 'mulita.presentation', 'mulita.ui', 'PyQt5'),
            'services': ('mulita.adapters', 'mulita.servers', 'mulita.presentation', 'mulita.ui', 'PyQt5'),
            'presentation': ('mulita.adapters', 'mulita.services', 'mulita.servers', 'mulita.ui', 'PyQt5'),
            'adapters': ('mulita.services', 'mulita.servers', 'mulita.presentation', 'mulita.ui', 'PyQt5'),
        }
        violations = []
        for layer, forbidden in rules.items():
            for path in (root / 'mulita' / layer).rglob('*.py'):
                package = '.'.join(path.relative_to(root).parts[:-1])
                for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                    if isinstance(node, ast.Import):
                        modules = [alias.name for alias in node.names]
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ''
                        if node.level:
                            module = importlib.util.resolve_name('.' * node.level + module, package)
                        modules = [module, *(module + '.' + alias.name for alias in node.names)]
                    else:
                        continue
                    for module in modules:
                        if any(module == name or module.startswith(name + '.') for name in forbidden):
                            violations.append(f'{path.relative_to(root)}:{node.lineno}: {module}')
        self.assertEqual(violations, [])

    def test_importing_services_and_translations_does_not_load_server_or_adapter_modules(self):
        subprocess.run([sys.executable, '-c',
            "import sys; from mulita.presentation.i18n import Translator; "
            "from mulita.services.diagnostics import PingService; "
            "assert Translator('en').tr('journalExport', name='ping.csv') == 'The file ping.csv was exported.'; "
            "assert not any(name.startswith(('mulita.servers', 'mulita.adapters', 'mulita.ui', 'PyQt5')) for name in sys.modules)"],
            cwd=Path(__file__).resolve().parents[1], check=True, timeout=15)
