import logging
from pathlib import Path

log = logging.getLogger(__name__)


def determine_venv_paths(project_path: Path) -> tuple[Path, Path]:
    """
    Given a project path, returns the venv-bin-path and the venv-path.

    Used, by calling code, to build:
        local_scoped_env['PATH'] = f'{venv_bin_path}:{local_scoped_env["PATH"]}'  # prioritizes venv-path
        local_scoped_env['VIRTUAL_ENV'] = str(venv_path)
    ...for use in subprocess.run() calls like:
        subprocess.run(the_command, check=True, env=local_scoped_env)  # so all installs will go to the venv

    Essentially allows a subprocess.run() command to act as if it's running in an activated venv.
    """
    venv_bin_path: Path = project_path.parent / 'env' / 'bin'
    venv_bin_path = venv_bin_path.resolve()
    venv_path: Path = project_path.parent / 'env'
    venv_path = venv_path.resolve()
    log.debug(f'venv_bin_path: ``{venv_bin_path}``')
    log.debug(f'venv_path: ``{venv_path}``')
    return (venv_bin_path, venv_path)
