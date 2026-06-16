let paperWs = null;
let paperTaskId = null;
let chatMessages = [];
let artifactRecords = [];
let stageReviewRecords = [];

const STAGE_LABELS = {
  deepagent_reasoning: 'DeepAgent 编排',
  ingest_inputs: '整理输入',
  understand_problem: '理解赛题',
  audit_data: '审计数据',
  retrieve_evidence: '检索证据',
  plan_modeling: '规划模型',
  run_experiments: '生成实验',
  draft_paper: '起草论文',
  review_and_revise: '质量评审',
  package_submission: '打包提交',
};

function simpleMarkdown(text) {
  return String(text || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>');
}

function escapeHTML(text) {
  return String(text || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function classToken(text) {
  return String(text || '')
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'unknown';
}

function setStatus(msg, color) {
  const el = document.getElementById('status');
  if (!el) return;
  el.textContent = msg;
  el.style.color = color || '';
}

function setRunState(text, color) {
  const el = document.getElementById('run-state');
  if (!el) return;
  el.textContent = text;
  el.style.color = color || '';
}

function parsePathLines(id) {
  const el = document.getElementById(id);
  if (!el) return [];
  return el.value
    .split('\n')
    .map(v => v.trim())
    .filter(Boolean);
}

function clearChat() {
  const log = document.getElementById('chat-log');
  if (log) log.innerHTML = '';
  chatMessages = [];
  artifactRecords = [];
  stageReviewRecords = [];
  renderStages({});
  renderArtifacts();
  renderStageReviews();
  document.getElementById('btn-followup').disabled = true;
  document.getElementById('btn-download-all').disabled = true;
}

function appendChat(role, content, meta) {
  const log = document.getElementById('chat-log');
  if (!log) return;
  const empty = log.querySelector('.chat-empty');
  if (empty) empty.remove();
  const item = document.createElement('article');
  item.className = 'chat-message ' + role;
  const label = role === 'user' ? '你' : role === 'assistant' ? 'DeepAgent' : '系统';
  item.innerHTML =
    '<div class="chat-meta">' + label + (meta ? ' · ' + meta : '') + '</div>' +
    '<div class="chat-body"><p>' + simpleMarkdown(content) + '</p></div>';
  log.appendChild(item);
  log.scrollTop = log.scrollHeight;
  if (role === 'user' || role === 'assistant') {
    chatMessages.push({ role, content: String(content || '') });
  }
}

function appendEvent(content, stage) {
  appendChat('system', content, stage ? (STAGE_LABELS[stage] || stage) : 'event');
}

function renderStages(stageStatus) {
  const el = document.getElementById('stage-list');
  if (!el) return;
  const stages = Array.from(new Set([...Object.keys(STAGE_LABELS), ...Object.keys(stageStatus)]));
  el.innerHTML = stages.map(stage => {
    const status = stageStatus[stage] || 'pending';
    return '<div class="stage-row ' + classToken(status) + '">' +
      '<span>' + (STAGE_LABELS[stage] || stage) + '</span>' +
      '<strong>' + status + '</strong>' +
      '</div>';
  }).join('');
}

const stageStatus = {};
renderStages(stageStatus);

function updateStage(stage, status) {
  stageStatus[stage] = status;
  renderStages(stageStatus);
}

function renderArtifacts() {
  const list = document.getElementById('artifact-list');
  if (!list) return;
  if (!artifactRecords.length) {
    list.innerHTML = '<div class="artifact-note">完成后会显示论文、代码、报告和 run.json。</div>';
    return;
  }
  const seen = new Set();
  list.innerHTML = artifactRecords
    .filter(item => {
      const key = item.path || item.name;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .map(item => '<div class="artifact-item"><strong>' + (item.name || 'artifact') + '</strong><span>' +
      (item.kind || 'file') + '</span><small>' + (item.path || '') + '</small></div>')
    .join('');
}

function addArtifact(event) {
  artifactRecords.push({
    name: event.name || (event.path ? event.path.split('/').pop() : 'artifact'),
    path: event.path || '',
    kind: event.kind || '',
  });
  renderArtifacts();
  document.getElementById('btn-download-all').disabled = false;
}

function addStageReview(event) {
  const index = stageReviewRecords.findIndex(item => item.output_id === event.output_id);
  if (index >= 0) {
    stageReviewRecords[index] = { ...stageReviewRecords[index], ...event };
  } else {
    stageReviewRecords.push(event);
  }
  renderStageReviews();
}

function markStageReviewInvalidated(event) {
  const index = stageReviewRecords.findIndex(item => item.output_id === event.output_id);
  if (index >= 0) {
    stageReviewRecords[index] = { ...stageReviewRecords[index], ...event, status: 'stale' };
  } else {
    stageReviewRecords.push({ ...event, status: 'stale' });
  }
  updateStage(event.stage, 'stale');
  renderStageReviews();
}

function renderStageReviews() {
  const list = document.getElementById('stage-review-list');
  if (!list) return;
  if (!stageReviewRecords.length) {
    list.innerHTML = '<div class="artifact-note">阶段产物生成后会在这里进入审阅队列。</div>';
    return;
  }
  list.innerHTML = stageReviewRecords.map(item => {
    const payload = item.review_payload || {};
    const keys = Object.keys(payload).slice(0, 5);
    const fields = keys.length
      ? '<dl>' + keys.map(key => {
          const value = Array.isArray(payload[key]) ? payload[key].join(', ') :
            (typeof payload[key] === 'object' && payload[key] !== null ? JSON.stringify(payload[key]) : payload[key]);
          return '<dt>' + escapeHTML(key) + '</dt><dd>' + escapeHTML(String(value || '')) + '</dd>';
        }).join('') + '</dl>'
      : '<small>暂无结构化字段</small>';
    const staleNote = item.status === 'stale'
      ? '<div class="stage-review-stale">已过期，仅供对比</div>'
      : '';
    return '<article class="stage-review-card ' + classToken(item.status) + '">' +
      '<div class="stage-review-head"><strong>' + escapeHTML(item.stage_label || STAGE_LABELS[item.stage] || item.stage || '阶段产物') + '</strong>' +
      '<span>v' + escapeHTML(item.version || '') + ' · ' + escapeHTML(item.status || '') + '</span></div>' +
      '<p>' + escapeHTML(item.summary || '') + '</p>' + staleNote + fields +
      '</article>';
  }).join('');
}

async function startPaperRun() {
  const question = document.getElementById('question').value.trim();
  if (!question) {
    setStatus('请先输入赛题或研究任务', 'var(--red)');
    return;
  }
  clearChat();
  Object.keys(stageStatus).forEach(k => delete stageStatus[k]);
  renderStages(stageStatus);
  appendChat('user', question);
  await startPaperTask(question);
}

async function sendFollowup() {
  const input = document.getElementById('followup-input');
  const question = input.value.trim();
  if (!question) return;
  input.value = '';
  appendChat('user', question);
  await startPaperTask(question);
}

async function startPaperTask(question) {
  setRunState('Starting');
  setStatus('启动论文工作流...');
  document.getElementById('btn-paper').disabled = true;
  document.getElementById('btn-followup').disabled = true;

  try {
    const resp = await fetch('/api/paper/chat/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        data_files: parsePathLines('data-files'),
        reference_files: parsePathLines('reference-files'),
        messages: chatMessages.slice(-10),
      }),
    });
    const data = await resp.json();
    if (!resp.ok || data.error) {
      throw new Error(data.error || 'HTTP ' + resp.status);
    }
    paperTaskId = data.task_id;
    connectPaperWS(paperTaskId);
    setStatus('论文工作流运行中...');
  } catch (e) {
    setStatus('启动失败: ' + e.message, 'var(--red)');
    setRunState('Error', 'var(--red)');
    document.getElementById('btn-paper').disabled = false;
    document.getElementById('btn-followup').disabled = false;
  }
}

function connectPaperWS(taskId) {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  paperWs = new WebSocket(proto + '//' + location.host + '/ws/paper/' + taskId);

  paperWs.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    handlePaperEvent(msg);
  };
  paperWs.onerror = () => {
    setStatus('论文流连接失败', 'var(--red)');
    setRunState('Error', 'var(--red)');
  };
  paperWs.onclose = () => {
    paperWs = null;
    document.getElementById('btn-paper').disabled = false;
  };
}

function handlePaperEvent(msg) {
  switch (msg.type) {
    case 'start':
      setRunState('Running');
      appendEvent('已创建论文生产任务。');
      break;
    case 'stage':
      updateStage(msg.stage, msg.status);
      appendEvent((msg.label || msg.stage) + '：' + msg.status, msg.stage);
      break;
    case 'tool':
      appendEvent('工具 ' + msg.name + '：' + msg.status, msg.stage);
      break;
    case 'artifact':
      addArtifact(msg);
      appendEvent('生成产物：' + (msg.name || msg.path), msg.stage);
      break;
    case 'quality_gate':
      appendEvent('质量门 ' + msg.gate_name + '：' + (msg.passed ? '通过' : '未通过') + '，得分 ' + msg.score, msg.stage);
      break;
    case 'stage_review_created':
    case 'stage_review_updated':
      addStageReview(msg);
      appendEvent('阶段产物待审阅：' + (msg.stage_label || STAGE_LABELS[msg.stage] || msg.stage || ''), msg.stage);
      break;
    case 'stage_invalidated':
      markStageReviewInvalidated(msg);
      appendEvent('阶段产物已过期：' + (msg.stage_label || STAGE_LABELS[msg.stage] || msg.stage || ''), msg.stage);
      break;
    case 'message':
      appendChat(msg.role || 'assistant', msg.content || '');
      break;
    case 'done':
      if (msg.status === 'completed') {
        setRunState('Complete', 'var(--green)');
        setStatus('✓ 论文提交包已生成', 'var(--green)');
        appendChat('assistant', '运行完成：' + (msg.summary || msg.run_id || 'done'));
      } else if (msg.status === 'partial') {
        setRunState('Needs input', 'var(--orange)');
        setStatus('需要继续补充信息或修正指令', 'var(--orange)');
        appendChat('assistant', '当前尚未形成完整提交包：' + (msg.summary || '请继续补充赛题、数据或约束。'));
      } else {
        setRunState(msg.status || 'Done');
        setStatus('运行结束：' + (msg.status || 'done'));
        appendChat('assistant', '运行结束：' + (msg.summary || msg.run_id || 'done'));
      }
      (msg.artifacts || []).forEach(addArtifact);
      document.getElementById('btn-followup').disabled = false;
      break;
    case 'error':
      setRunState('Error', 'var(--red)');
      setStatus('✗ ' + msg.message, 'var(--red)');
      appendChat('system', msg.message || '运行失败');
      document.getElementById('btn-followup').disabled = false;
      break;
  }
}

async function searchRAG() {
  const q = document.getElementById('rag-query').value.trim();
  if (!q) return;
  try {
    const resp = await fetch('/api/rag/query?q=' + encodeURIComponent(q));
    const data = await resp.json();
    const el = document.getElementById('rag-results');
    if (!data.chunks.length) { el.innerHTML = '无匹配结果'; return; }
    el.innerHTML = data.chunks.map((c, i) =>
      `<div><strong>${i + 1}. ${c.source}</strong><br>${c.content}</div>`
    ).join('');
  } catch (e) {
    document.getElementById('rag-results').innerHTML = '检索失败';
  }
}

async function rebuildRAG() {
  try {
    const resp = await fetch('/api/rag/rebuild', { method: 'POST' });
    const data = await resp.json();
    document.getElementById('rag-status').textContent =
      '已就绪 · ' + data.files + ' 文件, ' + data.chunks + ' 片段';
  } catch (e) {
    document.getElementById('rag-status').textContent = '重建失败';
  }
}

async function loadSkills() {
  try {
    const resp = await fetch('/api/skills');
    const data = await resp.json();
    const el = document.getElementById('skills-list');
    el.innerHTML =
      '<strong>Rules:</strong> ' + data.rules.join(', ') + '<br>' +
      '<strong>Templates:</strong> ' + data.viz_templates.length + ' 个可视化模板<br>' +
      '<strong>Tools:</strong> ' + data.tools.join(', ');
  } catch (e) {
    document.getElementById('skills-list').textContent = '加载失败';
  }
}

function downloadAll() {
  const content = chatMessages.map(msg => msg.role + ': ' + msg.content).join('\n\n');
  downloadBlob(content, 'paper-chat-transcript.md', 'text/markdown');
  setStatus('已导出当前对话', 'var(--green)');
}

function downloadBlob(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType || 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function onPDFSelected() {
  const fileInput = document.getElementById('pdf-file');
  const file = fileInput.files[0];
  if (!file) return;

  const nameEl = document.getElementById('pdf-name');
  const statusEl = document.getElementById('upload-status');
  const questionEl = document.getElementById('question');

  nameEl.textContent = file.name;
  statusEl.textContent = '提取中...';
  statusEl.style.color = '';

  const formData = new FormData();
  formData.append('file', file);

  fetch('/api/upload/pdf', { method: 'POST', body: formData })
    .then(function(resp) {
      if (!resp.ok) {
        return resp.json().then(function(d) { throw new Error(d.error || 'HTTP ' + resp.status); });
      }
      return resp.json();
    })
    .then(function(data) {
      if (data.error) {
        statusEl.textContent = '✗ ' + data.error;
        statusEl.style.color = 'var(--red)';
        return;
      }
      questionEl.value = data.text;
      statusEl.textContent = '✓ ' + data.pages + ' 页, ' + data.full_length + ' 字符';
      statusEl.style.color = 'var(--green)';
      setStatus('题目已从 PDF 提取，可开始论文生产', 'var(--green)');
    })
    .catch(function(e) {
      statusEl.textContent = '✗ ' + e.message;
      statusEl.style.color = 'var(--red)';
      setStatus('PDF 上传失败', 'var(--red)');
    });
  fileInput.value = '';
}

loadSkills();
