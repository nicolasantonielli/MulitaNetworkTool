"""Prepare related exports before publishing; roll back this operation on failure."""
from contextlib import contextmanager
from pathlib import Path
import os
import shutil
import tempfile


@contextmanager
def export_bundle(destinations: tuple[Path, ...]):
    """Never overwrite existing files. This is not a power-loss atomic transaction."""
    created = []
    with tempfile.TemporaryDirectory(prefix='.export-', dir=destinations[0].parent) as folder:
        staged = tuple(Path(folder) / path.name for path in destinations)
        yield staged
        try:
            for source, destination in zip(staged, destinations):
                with destination.open('xb') as output:
                    created.append(destination)
                    with source.open('rb') as incoming:
                        shutil.copyfileobj(incoming, output)
                    output.flush()
                    os.fsync(output.fileno())
        except BaseException:
            for path in reversed(created):
                path.unlink(missing_ok=True)
            raise
