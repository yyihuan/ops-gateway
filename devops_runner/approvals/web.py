"""Web approval backend with external static assets."""

from __future__ import annotations

import json
import pathlib
import sys
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from typing import Any

from devops_runner.approvals.base import ApprovalBackend
from devops_runner.approvals.mode_store import ApprovalModeStore
from devops_runner.approvals.web_state import WebApprovalState
from devops_runner.errors import CommandFailure, RunnerError


def _load_static_text(name: str) -> str:
    """Load a bundled text asset from the Web approval static package."""

    return resources.files("devops_runner.approvals.static").joinpath(name).read_text(encoding="utf-8")


def _load_static_bytes(name: str) -> bytes:
    """Load a bundled binary asset from the Web approval static package."""

    return resources.files("devops_runner.approvals.static").joinpath(name).read_bytes()


class WebApprovalBackend(ApprovalBackend):
    """Approval backend that exposes prompts over a local HTTP server."""

    def __init__(
        self,
        *,
        plan: dict[str, Any],
        task_id: str,
        run_id: str,
        run_dir: pathlib.Path,
        audit_log_path: pathlib.Path,
        plan_id: str,
        plan_title: str,
        plan_summary_text: str,
        approval_threshold: str,
        global_default_mode: str,
        initial_run_approval_mode: str,
        approval_mode_state_file: pathlib.Path,
        approval_mode_store: ApprovalModeStore,
        host: str,
        port: int,
        log_event: Callable[..., None],
        step_requires_approval: Callable[[dict[str, Any]], bool],
        mode_auto_approves_step: Callable[[str, dict[str, Any]], bool],
        validate_step: Callable[[dict[str, Any], int], None],
        sync_plan_copy: Callable[[], None],
        execute_phase: Callable[[dict[str, Any], str], None],
        render_step_text: Callable[[dict[str, Any]], str],
        render_rollback_prompt: Callable[[dict[str, Any], CommandFailure], str],
    ) -> None:
        """Store explicit dependencies for the Web approval workflow."""

        self._plan = plan
        self._task_id = task_id
        self._run_id = run_id
        self._run_dir = run_dir
        self._audit_log_path = audit_log_path
        self._plan_id = plan_id
        self._plan_title = plan_title
        self._plan_summary_text = plan_summary_text
        self._approval_threshold = approval_threshold
        self._global_default_mode = global_default_mode
        self._initial_run_approval_mode = initial_run_approval_mode
        self._approval_mode_state_file = approval_mode_state_file
        self._approval_mode_store = approval_mode_store
        self._host = host
        self._port = port
        self._log_event = log_event
        self._step_requires_approval = step_requires_approval
        self._mode_auto_approves_step = mode_auto_approves_step
        self._validate_step = validate_step
        self._sync_plan_copy = sync_plan_copy
        self._execute_phase = execute_phase
        self._render_step_text = render_step_text
        self._render_rollback_prompt = render_rollback_prompt
        self.state = WebApprovalState()
        self.server: ThreadingHTTPServer | None = None
        self.server_thread: threading.Thread | None = None
        self.prompt_counter = 0

    def _next_prompt_id(self) -> str:
        """Return a monotonically increasing prompt identifier."""

        self.prompt_counter += 1
        return f"prompt-{self.prompt_counter}"

    def _set_approval_mode(self, mode: str) -> dict[str, Any]:
        """Update the current run approval mode through the browser UI."""

        result = self.state.set_run_approval_mode(
            mode,
            auto_submit_current_prompt=(mode == "auto_low_risk"),
        )
        if result.get("ok"):
            self._log_event(
                "run_approval_mode_changed",
                backend="web",
                run_approval_mode=mode,
                global_default_mode=self.state.global_default_mode,
                auto_submitted=result.get("auto_submitted", False),
            )
        return result

    def _set_global_default_mode(self, mode: str) -> dict[str, Any]:
        """Persist and apply the global default approval mode."""

        try:
            self._approval_mode_store.write_mode(mode)
        except (OSError, RunnerError) as exc:
            return {"ok": False, "message": f"failed to persist global approval mode: {exc}"}
        result = self.state.set_global_default_mode(
            mode,
            apply_to_run=True,
            auto_submit_current_prompt=(mode == "auto_low_risk"),
        )
        if result.get("ok"):
            self._log_event(
                "global_approval_mode_changed",
                backend="web",
                global_default_mode=mode,
                run_approval_mode=self.state.run_approval_mode,
                auto_submitted=result.get("auto_submitted", False),
                state_file=str(self._approval_mode_state_file),
            )
        return result

    def _build_server(self) -> ThreadingHTTPServer:
        """Construct the threaded HTTP server used by the approval page."""

        backend = self

        class Handler(BaseHTTPRequestHandler):
            def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _send_asset(self, body: bytes, *, content_type: str, status: int = 200) -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                if self.path in {"/", "/index.html"}:
                    self._send_asset(_load_static_bytes("index.html"), content_type="text/html; charset=utf-8")
                    return
                if self.path == "/static/styles.css":
                    self._send_asset(_load_static_bytes("styles.css"), content_type="text/css; charset=utf-8")
                    return
                if self.path == "/static/app.js":
                    self._send_asset(
                        _load_static_bytes("app.js"),
                        content_type="application/javascript; charset=utf-8",
                    )
                    return
                if self.path == "/api/state":
                    self._send_json(backend.state.snapshot())
                    return
                self._send_json({"ok": False, "message": "not found"}, status=404)

            def do_POST(self) -> None:
                if self.path == "/api/mode":
                    content_length = int(self.headers.get("Content-Length", "0"))
                    raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
                    try:
                        payload = json.loads(raw_body.decode("utf-8"))
                    except json.JSONDecodeError:
                        self._send_json({"ok": False, "message": "invalid json body"}, status=400)
                        return
                    action = str(payload.get("action", "")).strip().lower()
                    if action == "enable_auto_low_risk_run":
                        result = backend._set_approval_mode("auto_low_risk")
                    elif action == "disable_auto_run":
                        result = backend._set_approval_mode("manual")
                    elif action == "set_global_auto_low_risk":
                        result = backend._set_global_default_mode("auto_low_risk")
                    elif action == "set_global_manual":
                        result = backend._set_global_default_mode("manual")
                    else:
                        self._send_json({"ok": False, "message": "unsupported mode action"}, status=400)
                        return
                    self._send_json(result, status=200 if result["ok"] else 409)
                    return
                if self.path != "/api/decision":
                    self._send_json({"ok": False, "message": "not found"}, status=404)
                    return
                content_length = int(self.headers.get("Content-Length", "0"))
                raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
                try:
                    payload = json.loads(raw_body.decode("utf-8"))
                except json.JSONDecodeError:
                    self._send_json({"ok": False, "message": "invalid json body"}, status=400)
                    return
                decision = str(payload.get("decision", "")).strip().lower()
                if decision not in {"yes", "no", "edit"}:
                    self._send_json({"ok": False, "message": "decision must be yes, no, or edit"}, status=400)
                    return
                prompt_id = str(payload.get("prompt_id", "")).strip()
                edited_step_json = payload.get("edited_step_json")
                if edited_step_json is not None and not isinstance(edited_step_json, str):
                    self._send_json({"ok": False, "message": "edited_step_json must be a string"}, status=400)
                    return
                result = backend.state.submit_decision(
                    prompt_id=prompt_id,
                    decision=decision,
                    edited_step_json=edited_step_json,
                )
                self._send_json(result, status=200 if result["ok"] else 409)

            def log_message(self, format: str, *args: Any) -> None:
                return

        class Server(ThreadingHTTPServer):
            allow_reuse_address = True

        return Server((self._host, self._port), Handler)

    def _display_host(self) -> str:
        """Return the browser-facing host string for the running server."""

        if self.server is None:
            return self._host
        server_host = self.server.server_address[0]
        if server_host in {"0.0.0.0", "::"}:
            return "127.0.0.1"
        return server_host

    def _wait_for_prompt_decision(
        self,
        *,
        prompt_kind: str,
        step: dict[str, Any],
        summary_text: str,
        editable_step_json: str | None,
        error_message: str | None = None,
    ) -> dict[str, Any] | None:
        """Publish a prompt and wait for a browser submission."""

        prompt = {
            "id": self._next_prompt_id(),
            "kind": prompt_kind,
            "step_id": step["id"],
            "title": step["title"],
            "summary_text": summary_text,
            "editable_step_json": editable_step_json,
            "error": error_message or "",
            "risk_level": step["risk"]["level"],
            "auto_approvable": self._mode_auto_approves_step("auto_low_risk", step),
        }
        self.state.set_prompt(prompt)
        print(f"web approval pending: {self.state.server_url} ({prompt_kind} for {step['id']})")
        return self.state.wait_for_submission(prompt["id"])

    def start(self) -> None:
        """Start the HTTP server and publish the initial state snapshot."""

        self.server = self._build_server()
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        display_host = self._display_host()
        display_port = self.server.server_address[1]
        server_url = f"http://{display_host}:{display_port}"
        self.state.configure(
            server_url=server_url,
            task_id=self._task_id,
            run_id=self._run_id,
            run_dir=self._run_dir,
            audit_log_path=self._audit_log_path,
            plan_id=self._plan_id,
            plan_title=self._plan_title,
            plan_summary_text=self._plan_summary_text,
            global_default_mode=self._global_default_mode,
            run_approval_mode=self._initial_run_approval_mode,
            approval_threshold=self._approval_threshold,
        )
        print(f"web approval url: {server_url}")
        print("web approval mode: open the page in a browser and use the buttons there.")
        print("web approval mode: the page auto-refreshes every second.")

    def stop(self) -> None:
        """Stop the HTTP server and release blocked request handlers."""

        self.state.mark_shutdown()
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        if self.server_thread is not None:
            self.server_thread.join(timeout=2)

    def on_event(self, payload: dict[str, Any]) -> None:
        """Feed audit events into the browser-visible state."""

        self.state.record_event(payload)

    def approve_step(self, step_index: int) -> dict[str, Any] | None:
        """Expose a step approval prompt through the browser workflow."""

        current = self._plan["steps"][step_index]
        error_message = None
        editable_step_json = json.dumps(current, ensure_ascii=False, indent=2)
        while True:
            if not self._step_requires_approval(current):
                self._log_event(
                    "step_auto_approved",
                    step_id=current["id"],
                    step_title=current["title"],
                    approval_origin="threshold",
                    approval_threshold=self._approval_threshold,
                )
                return current
            active_mode = self.state.get_run_approval_mode()
            if self._mode_auto_approves_step(active_mode, current):
                self._log_event(
                    "step_auto_approved",
                    step_id=current["id"],
                    step_title=current["title"],
                    approval_origin="mode",
                    approval_mode=active_mode,
                )
                return current
            submission = self._wait_for_prompt_decision(
                prompt_kind="step_approval",
                step=current,
                summary_text=self._render_step_text(current),
                editable_step_json=editable_step_json,
                error_message=error_message,
            )
            if submission is None:
                raise RunnerError("web approval backend stopped while waiting for a decision")
            error_message = None
            decision = submission["decision"]
            if decision == "yes":
                self.state.clear_prompt()
                self._log_event("step_approved", step_id=current["id"], step_title=current["title"])
                return current
            if decision == "no":
                self.state.clear_prompt()
                self._log_event("step_rejected", step_id=current["id"], step_title=current["title"])
                return None
            if decision == "edit":
                edited_text = submission.get("edited_step_json") or ""
                try:
                    edited = json.loads(edited_text)
                    if not isinstance(edited, dict):
                        raise RunnerError("edited step must be a JSON object")
                    self._validate_step(edited, 0)
                    self._plan["steps"][step_index] = edited
                    current = edited
                    self._sync_plan_copy()
                    self._log_event("step_edited", step_id=current["id"], step_title=current["title"])
                    self.state.clear_prompt()
                    editable_step_json = json.dumps(current, ensure_ascii=False, indent=2)
                except (json.JSONDecodeError, RunnerError) as exc:
                    error_message = f"edit error: {exc}"
                    editable_step_json = edited_text
                    self._log_event(
                        "step_edit_failed",
                        step_id=current["id"],
                        step_title=current["title"],
                        error=str(exc),
                    )
                continue

    def prompt_rollback(self, step: dict[str, Any], error: CommandFailure) -> None:
        """Expose rollback approval through the browser workflow."""

        if not step["rollback"]:
            self._log_event("rollback_skipped", step_id=step["id"], reason="empty_rollback")
            return
        while True:
            submission = self._wait_for_prompt_decision(
                prompt_kind="rollback_prompt",
                step=step,
                summary_text=self._render_rollback_prompt(step, error),
                editable_step_json=None,
            )
            if submission is None:
                raise RunnerError("web approval backend stopped while waiting for rollback decision")
            decision = submission["decision"]
            if decision == "yes":
                self.state.clear_prompt()
                self._log_event("rollback_approved", step_id=step["id"], reason=str(error))
                try:
                    self._execute_phase(step, "rollback")
                    self._log_event("rollback_finished", step_id=step["id"], status="success")
                except RunnerError as rollback_exc:
                    rollback_data: dict[str, Any] = {
                        "step_id": step["id"],
                        "status": "failed",
                        "error": str(rollback_exc),
                    }
                    if isinstance(rollback_exc, CommandFailure):
                        rollback_data.update(
                            {
                                "phase": rollback_exc.phase,
                                "command_id": rollback_exc.command_id,
                                "returncode": rollback_exc.returncode,
                            }
                        )
                    self._log_event("rollback_failed", **rollback_data)
                    print(f"rollback also failed: {rollback_exc}", file=sys.stderr)
                return
            if decision == "no":
                self.state.clear_prompt()
                self._log_event("rollback_declined", step_id=step["id"], reason=str(error))
                return
            self.state.update_prompt_error("rollback only accepts yes or no")


__all__ = ["WebApprovalBackend"]
