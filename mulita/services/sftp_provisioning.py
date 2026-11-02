"""Prepare SFTP accounts, credentials and SSH configuration with explicit cleanup."""
from pathlib import Path, PurePosixPath
from mulita.core.errors import CommandFailedError, ValidationError
from mulita.core.messages import message
from mulita.services.server_plan import ServerPlan

USER_MARK = 'Mulita SFTP temporal'
UPLOADS = 'respaldos'

class SftpProvisioner:
    def __init__(self, runner, commands, state_dir: Path, capture_dir, posix: bool):
        self._runner = runner
        self._commands = commands
        self._state_dir = state_dir
        self._capture_dir = capture_dir
        self._posix = posix

    def prepare(self, user: str, password: str, writable: bool, port: int, address: str) -> ServerPlan:
        entry = self._runner.run(self._commands.user_entry(user))
        if entry.ok and entry.stdout.strip():
            if USER_MARK not in entry.stdout:
                raise ValidationError(message('sftpUserTaken', user=user))
        else:
            self._must(self._commands.user_add(user, USER_MARK))

        uploads = PurePosixPath(self._capture_dir) / UPLOADS

        def cleanup() -> None:
            # Las subidas quedan a nombre de root: un usuario nuevo con otro numero no las pierde.
            self._runner.run(self._commands.change_owner('root:root', str(uploads), recursive=True))
            self._runner.run(self._commands.user_delete(user))

        try:
            self._make_dir(Path(uploads), 'serverFolder')
            folder = self._state('sftp')
            host_key = folder / 'host_ed25519'
            if self._posix and not host_key.exists():
                self._must(self._commands.ssh_host_key(str(host_key)))
            config = folder / 'sshd_config'
            self._write_sshd_config(config, host_key, port, address, user, writable)
            self._must(self._commands.set_password(), f'{user}:{password}\n')
            self._must(self._commands.change_owner(user, str(uploads), recursive=True))
            if self._posix:
                Path('/run/sshd').mkdir(mode=0o755, parents=True, exist_ok=True)
        except Exception:
            cleanup()
            raise
        return ServerPlan(self._commands.sftp_server(str(config)), cleanup)


    def _make_dir(self, path: Path, error_key: str) -> None:
        if not self._posix:
            return
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CommandFailedError(message(error_key)) from exc


    def _state(self, name: str) -> Path:
        path = self._state_dir / name
        self._make_dir(path, 'serverFolder')
        return path


    def _write_sshd_config(self, path: Path, host_key: Path, port: int, address: str,
                           user: str, writable: bool) -> None:
        lines = [f'Port {port}']
        if address:
            lines.append(f'ListenAddress {address}')
        lines += [
            f'HostKey {host_key}', 'PidFile none', 'UsePAM no', 'LogLevel VERBOSE',
            'LoginGraceTime 30', 'MaxAuthTries 3', 'PermitRootLogin no',
            'PasswordAuthentication yes', 'PubkeyAuthentication no',
            'ChallengeResponseAuthentication no', f'AllowUsers {user}',
            'AllowTcpForwarding no', 'X11Forwarding no', 'PermitTTY no',
            'Subsystem sftp internal-sftp',
            f'Match User {user}',
            f'    ChrootDirectory {self._capture_dir}',
            f'    ForceCommand internal-sftp{"" if writable else " -R"}',
        ]
        if not self._posix:
            return
        try:
            path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        except OSError as exc:
            raise CommandFailedError(message('serverFolder')) from exc


    def _must(self, argv: list[str], input_text: str | None = None) -> None:
        result = (self._runner.run(argv, input_text=input_text) if input_text is not None
                  else self._runner.run(argv))
        if not result.ok:
            raise CommandFailedError(message('serverPrepare', detail=_first_line(result.text)), result)


def _first_line(text: str) -> str:
    return next((line.strip() for line in (text or '').splitlines() if line.strip()), '')[:180]
