"""Pruebas del instalador unificado, sin ejecutar APT ni modificar el sistema."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'install-lite.sh').read_text(encoding='utf-8')
GIT_BASH = Path('C:/Program Files/Git/bin/bash.exe')
BASH = str(GIT_BASH) if GIT_BASH.exists() else shutil.which('bash')


def function(name):
    start = SOURCE.index(name + '() {')
    end = SOURCE.index('\n}\n', start) + 3
    return SOURCE[start:end]


@unittest.skipUnless(BASH, 'Bash no está disponible')
class InstallerTest(unittest.TestCase):
    def run_bash(self, script, env=None):
        return subprocess.run([BASH, '-s'], input=script, text=True, capture_output=True,
                              cwd=ROOT, env={**os.environ, **(env or {})}, timeout=15)

    def test_package_check_requires_installed_status(self):
        for status, success in (('install ok installed', True),
                                ('deinstall ok config-files', False),
                                ('install ok unpacked', False)):
            script = ("dpkg-query() { printf '%s' \"$TEST_STATUS\"; }\n" +
                      function('packages_ready') + '\npackages_ready python3 network-manager\n')
            result = self.run_bash(script, {'TEST_STATUS': status})
            self.assertEqual(result.returncode == 0, success, result.stderr)

    def test_missing_package_is_not_considered_installed(self):
        result = self.run_bash('dpkg-query() { return 1; }\n' + function('packages_ready') +
                               '\npackages_ready missing-package\n')
        self.assertNotEqual(result.returncode, 0)

    def test_screen_parameter_selects_profile_and_forwards_only_path_options(self):
        prefix = SOURCE.split('for command in apt-get', 1)[0]
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / 'installer-options.sh'
            script.write_text(prefix + '\nprintf "%s\\n" "$SCREEN" "$DISPLAY_HELPER" "${INSTALL_OPTIONS[@]}"\n',
                              encoding='utf-8', newline='\n')
            for screen, helper in (('5', 'scripts/configure_display.py'),
                                    ('7', 'scripts/configure_display_7.py')):
                result = self.run_bash('uname() { echo Linux; }; export -f uname\n'
                                       'bash "$TEST_SCRIPT" --capture-dir "/data with spaces" '
                                       + screen + ' --state-dir /private\n',
                                       {'TEST_SCRIPT': script.as_posix()})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines(), [screen, helper, '--capture-dir',
                                                              '/data with spaces', '--state-dir', '/private'])

    def test_cmdline_preserves_root_and_serial_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'cmdline.txt'
            original = 'console=serial0,115200 console=tty1 root=PARTUUID=abcd rootwait splash\n'
            path.write_text(original, encoding='utf-8')
            result = self.run_bash('set -e\nas_root() { "$@"; }\n' + function('configure_cmdline') +
                                   '\nconfigure_cmdline "$TEST_FILE"\nconfigure_cmdline "$TEST_FILE"\n',
                                   {'TEST_FILE': path.as_posix()})
            self.assertEqual(result.returncode, 0, result.stderr)
            updated = path.read_text(encoding='utf-8')
            self.assertIn('root=PARTUUID=abcd rootwait', updated)
            self.assertIn('console=serial0,115200', updated)
            self.assertNotIn('console=tty1', updated)
            self.assertEqual(updated.count('console=tty3'), 1)
            self.assertEqual(path.with_name('cmdline.txt.mulita-bak').read_text(), original)

    def test_invalid_cmdline_is_not_written(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'cmdline.txt'
            path.write_text('console=tty1\n', encoding='utf-8')
            result = self.run_bash(function('configure_cmdline') + '\nconfigure_cmdline "$TEST_FILE"\n',
                                   {'TEST_FILE': path.as_posix()})
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(path.read_text(), 'console=tty1\n')
            self.assertFalse(path.with_name('cmdline.txt.mulita-bak').exists())

    def test_missing_overlay_does_not_modify_boot_files(self):
        with tempfile.TemporaryDirectory() as folder:
            boot = Path(folder)
            (boot / 'config.txt').write_text('original=true\n')
            (boot / 'cmdline.txt').write_text('console=tty1 root=abc rootwait\n')
            result = self.run_bash('SCREEN=7\n' + function('select_display') + '\nselect_display\nboot_dir() { echo "$TEST_BOOT"; }\n' + function('configure_boot') +
                                   '\nconfigure_boot\n', {'TEST_BOOT': boot.as_posix()})
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((boot / 'config.txt').read_text(), 'original=true\n')
            self.assertEqual((boot / 'cmdline.txt').read_text(), 'console=tty1 root=abc rootwait\n')

    def test_help_and_invalid_arguments_exit_before_installation(self):
        for args, success in (('--help', True), ('', False), ('6', False), ('5 7', False), ('--unknown', False),
                              ('--capture-dir relative', False), ('--state-dir', False)):
            result = self.run_bash('uname() { echo Linux; }; export -f uname\n'
                                   'bash install-lite.sh ' + args + '\n')
            self.assertEqual(result.returncode == 0, success, result.stderr)
            self.assertNotIn('Instalando paquetes', result.stdout)
