"""Remote sync helpers for runner audit artifact export."""

from __future__ import annotations

import os
import pathlib
import posixpath
import pwd
import shlex
import subprocess
from collections.abc import Mapping
from typing import Any, TypedDict

from devops_runner.constants import VALID_SYNC_PHASES
from devops_runner.errors import RunnerError


class OperatorAccount(TypedDict):
    """Resolved operator identity used for rsync handoff."""

    user: str
    home: pathlib.Path
    uid: int
    gid: int


def split_remote_sync_target(target: str) -> tuple[str, str]:
    """Split a `host:path` rsync target into host and remote path."""

    if ":" not in target:
        raise RunnerError(f"remote sync target must be in host:path format: {target}")
    remote_host, remote_path = target.split(":", 1)
    if not remote_host or not remote_path:
        raise RunnerError(f"remote sync target must be in host:path format: {target}")
    return remote_host, remote_path


def find_operator_account(env: Mapping[str, str] | None = None) -> OperatorAccount | None:
    """Resolve the sudo-originating operator account, if any."""

    effective_env = dict(os.environ if env is None else env)
    sudo_user = effective_env.get("SUDO_USER")
    if not sudo_user:
        return None
    try:
        operator_entry = pwd.getpwnam(sudo_user)
    except KeyError:
        return None
    sudo_uid = effective_env.get("SUDO_UID")
    sudo_gid = effective_env.get("SUDO_GID")
    return {
        "user": sudo_user,
        "home": pathlib.Path(operator_entry.pw_dir),
        "uid": int(sudo_uid) if sudo_uid else operator_entry.pw_uid,
        "gid": int(sudo_gid) if sudo_gid else operator_entry.pw_gid,
    }


def find_operator_known_hosts(env: Mapping[str, str] | None = None) -> pathlib.Path | None:
    """Return the operator's known_hosts file when available."""

    operator_account = find_operator_account(env)
    if operator_account is None:
        return None
    known_hosts = operator_account["home"] / ".ssh" / "known_hosts"
    if known_hosts.is_file():
        return known_hosts
    return None


def sync_remote_run(
    *,
    plan: dict[str, Any],
    phase: str,
    step_id: str | None,
    base_run_root: pathlib.Path,
    run_dir: pathlib.Path,
    remote_sync_enabled: bool,
    log_event: Any,
    env: Mapping[str, str] | None = None,
) -> None:
    """Sync run artifacts to the configured remote target for the active phase."""

    if phase not in VALID_SYNC_PHASES:
        raise RunnerError(f"unsupported sync phase: {phase}")
    remote_sync = plan.get("remote_sync")
    if not remote_sync or not remote_sync.get("enabled") or not remote_sync_enabled:
        return
    phases = remote_sync.get("phases", ["plan_end"])
    if phase not in phases:
        return
    rsync_options = remote_sync.get("rsync_options", ["-az"])
    ssh_options = list(remote_sync.get("ssh_options", []))
    has_user_known_hosts = any(
        option == "UserKnownHostsFile" or option.startswith("UserKnownHostsFile=")
        for option in ssh_options
    )
    operator_known_hosts = find_operator_known_hosts(env)
    if operator_known_hosts is not None and not has_user_known_hosts:
        ssh_options.extend(["-o", f"UserKnownHostsFile={operator_known_hosts}"])
    try:
        remote_subdir = run_dir.relative_to(base_run_root).as_posix()
    except ValueError:
        remote_subdir = run_dir.name
    remote_host, remote_base_path = split_remote_sync_target(remote_sync["target"])
    remote_target_path = posixpath.join(remote_base_path.rstrip("/"), remote_subdir.rstrip("/"))
    target = f"{remote_host}:{remote_target_path.rstrip('/')}/"
    operator_account = find_operator_account(env)
    command_env = dict(os.environ if env is None else env)
    if operator_account is not None:
        ownership = f"{operator_account['uid']}:{operator_account['gid']}"
        prep_command = ["chown", "-R", ownership, str(run_dir)]
        log_event(
            "rsync_prepare_started",
            sync_phase=phase,
            step_id=step_id,
            command=prep_command,
            operator_user=operator_account["user"],
        )
        prep_result = subprocess.run(prep_command, capture_output=True, text=True)
        log_event(
            "rsync_prepare_finished",
            sync_phase=phase,
            step_id=step_id,
            command=prep_command,
            operator_user=operator_account["user"],
            returncode=prep_result.returncode,
            stdout=prep_result.stdout,
            stderr=prep_result.stderr,
        )
        if prep_result.returncode != 0:
            raise RunnerError(f"failed to hand off run artifacts to {operator_account['user']}")
        command_env["HOME"] = str(operator_account["home"])
        mkdir_command = [
            "sudo",
            "-u",
            operator_account["user"],
            "env",
            f"HOME={operator_account['home']}",
            "ssh",
            *ssh_options,
            remote_host,
            f"mkdir -p -- {shlex.quote(remote_target_path)}",
        ]
        command = [
            "sudo",
            "-u",
            operator_account["user"],
            "env",
            f"HOME={operator_account['home']}",
            "rsync",
            *rsync_options,
        ]
    else:
        mkdir_command = [
            "ssh",
            *ssh_options,
            remote_host,
            f"mkdir -p -- {shlex.quote(remote_target_path)}",
        ]
        command = ["rsync", *rsync_options]
    log_event("rsync_remote_prepare_started", sync_phase=phase, step_id=step_id, command=mkdir_command)
    mkdir_result = subprocess.run(mkdir_command, capture_output=True, text=True, env=command_env)
    log_event(
        "rsync_remote_prepare_finished",
        sync_phase=phase,
        step_id=step_id,
        command=mkdir_command,
        returncode=mkdir_result.returncode,
        stdout=mkdir_result.stdout,
        stderr=mkdir_result.stderr,
    )
    if mkdir_result.returncode != 0:
        if remote_sync.get("required", False):
            raise RunnerError(f"failed to prepare remote sync directory during {phase}")
        return
    if ssh_options:
        command.extend(["-e", "ssh " + " ".join(ssh_options)])
    command.extend([str(run_dir) + "/", target])
    log_event("rsync_started", sync_phase=phase, step_id=step_id, command=command)
    result = subprocess.run(command, capture_output=True, text=True, env=command_env)
    log_event(
        "rsync_finished",
        sync_phase=phase,
        step_id=step_id,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )
    if result.returncode != 0 and remote_sync.get("required", False):
        raise RunnerError(f"required rsync failed during {phase}")


__all__ = [
    "find_operator_account",
    "find_operator_known_hosts",
    "split_remote_sync_target",
    "sync_remote_run",
]
