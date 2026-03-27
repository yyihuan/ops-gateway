let currentState = null;
let lastPromptId = null;
let lastRunId = null;
let editDirty = false;

async function refreshState() {
  try {
    const response = await fetch('/api/state', { cache: 'no-store' });
    const data = await response.json();
    currentState = data;
    render(data);
  } catch (error) {
    document.getElementById('last-event').textContent = `connection lost: ${error}`;
  }
}

function render(data) {
  if (data.run_id && data.run_id !== lastRunId) {
    lastPromptId = null;
    editDirty = false;
  }
  lastRunId = data.run_id || null;
  document.title = data.run_id ? `Runner Approval - ${data.run_id}` : 'Runner Approval';
  document.getElementById('task-id').textContent = data.task_id || 'default';
  document.getElementById('run-id').textContent = data.run_id || '-';
  document.getElementById('plan-title').textContent = data.plan_title || '-';
  document.getElementById('current-step').textContent = data.current_step_id || '-';
  const phaseBits = [];
  if (data.current_phase) phaseBits.push(data.current_phase);
  if (data.current_command_id) phaseBits.push(data.current_command_id);
  document.getElementById('current-phase').textContent = phaseBits.length ? phaseBits.join(' / ') : '-';
  const finalStatus = data.final_status || 'running';
  const finalNode = document.getElementById('final-status');
  finalNode.textContent = data.final_error ? `${finalStatus} (${data.final_error})` : finalStatus;
  finalNode.className = data.final_status === 'success' ? 'status-ok' : (data.final_status && data.final_status !== 'running' ? 'status-bad' : '');
  const runApprovalMode = data.run_approval_mode || 'manual';
  const runApprovalModeNode = document.getElementById('run-approval-mode');
  runApprovalModeNode.textContent = runApprovalMode;
  runApprovalModeNode.className = runApprovalMode === 'auto_low_risk' ? 'mode-auto' : 'mode-manual';
  document.getElementById('run-mode-summary').textContent =
    runApprovalMode === 'auto_low_risk'
      ? 'auto_low_risk: auto-approve low-risk steps, plus steps explicitly allowlisted for this mode'
      : 'manual: every step approval requires a human click';
  const globalDefaultMode = data.global_default_mode || 'manual';
  const globalDefaultModeNode = document.getElementById('global-default-mode');
  globalDefaultModeNode.textContent = globalDefaultMode;
  globalDefaultModeNode.className = globalDefaultMode === 'auto_low_risk' ? 'mode-auto' : 'mode-manual';
  document.getElementById('approval-threshold').textContent = data.approval_threshold || 'low';
  document.getElementById('global-mode-summary').textContent =
    globalDefaultMode === 'auto_low_risk'
      ? 'global default auto_low_risk: new runs auto-approve low-risk steps and any explicit allowlisted steps'
      : 'global default manual: new runs require manual step approval';
  document.getElementById('last-event').textContent = data.last_event || '-';
  document.getElementById('plan-summary').textContent = data.plan_summary_text || '';
  document.getElementById('events').textContent = (data.recent_events || []).join('\n');

  const prompt = data.prompt;
  const promptSummary = document.getElementById('prompt-summary');
  const promptKind = document.getElementById('prompt-kind');
  const promptError = document.getElementById('prompt-error');
  const actions = document.getElementById('actions');
  const editWrapper = document.getElementById('edit-wrapper');
  const editButton = document.getElementById('edit-button');
  if (!prompt) {
    promptKind.textContent = 'No pending approval';
    promptSummary.textContent = 'Runner is executing or has completed.';
    promptError.textContent = '';
    actions.style.display = 'none';
    editWrapper.style.display = 'none';
    return;
  }
  promptKind.textContent = `${prompt.kind} | ${prompt.step_id || '-'} | ${prompt.title || ''}`;
  promptSummary.textContent = prompt.summary_text || '';
  promptError.textContent = prompt.error || '';
  actions.style.display = 'flex';
  if (prompt.kind === 'step_approval') {
    editWrapper.style.display = 'block';
    editButton.style.display = 'inline-block';
    const editJson = document.getElementById('edit-json');
    if (prompt.id !== lastPromptId) {
      editJson.value = prompt.editable_step_json || '';
      editDirty = false;
    } else if (!editDirty) {
      editJson.value = prompt.editable_step_json || '';
    }
  } else {
    editWrapper.style.display = 'none';
    editButton.style.display = 'none';
  }
  lastPromptId = prompt.id;
}

async function submitDecision(decision) {
  if (!currentState || !currentState.prompt) {
    alert('No pending approval.');
    return;
  }
  const payload = {
    prompt_id: currentState.prompt.id,
    decision: decision
  };
  if (decision === 'edit') {
    payload.edited_step_json = document.getElementById('edit-json').value;
  }
  const response = await fetch('/api/decision', {
    method: 'POST',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const result = await response.json();
  if (!result.ok) {
    alert(result.message);
  }
  editDirty = false;
  await refreshState();
  setTimeout(refreshState, 250);
  setTimeout(refreshState, 1000);
}

async function submitModeAction(action) {
  const response = await fetch('/api/mode', {
    method: 'POST',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action })
  });
  const result = await response.json();
  if (!result.ok) {
    alert(result.message);
  }
  await refreshState();
  setTimeout(refreshState, 250);
  setTimeout(refreshState, 1000);
}

document.addEventListener('DOMContentLoaded', () => {
  const editJson = document.getElementById('edit-json');
  editJson.addEventListener('input', () => {
    editDirty = true;
  });
  window.addEventListener('focus', () => {
    refreshState();
  });
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      refreshState();
    }
  });
});
refreshState();
setInterval(refreshState, 1000);
