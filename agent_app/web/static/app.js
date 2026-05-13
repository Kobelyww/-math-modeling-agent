let ws = null, taskId = null;

const agents = ['modeling', 'programming', 'writing', 'synthesis'];
const buffers = {};
agents.forEach(a => { buffers[a] = ''; });

function simpleMarkdown(text) {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>');
}

function setStatus(msg, color) {
  const el = document.getElementById('status');
  el.textContent = msg;
  el.style.color = color || '';
}

function showSpinner(agent) {
  document.getElementById('spin-' + agent).classList.remove('hidden');
  document.getElementById('out-' + agent).classList.add('cursor');
}

function hideSpinner(agent) {
  document.getElementById('spin-' + agent).classList.add('hidden');
  document.getElementById('out-' + agent).classList.remove('cursor');
}

function setProgress(agent, pct) {
  document.getElementById('bar-' + agent).style.width = pct + '%';
}

async function startSolve() {
  const question = document.getElementById('question').value.trim();
  if (!question) { setStatus('请输入问题', 'var(--red)'); return; }

  const strategy = document.getElementById('strategy').value;
  agents.forEach(a => {
    buffers[a] = '';
    document.getElementById('out-' + a).innerHTML = '';
    setProgress(a, 0);
    showSpinner(a);
  });
  setStatus('启动中...');

  try {
    const resp = await fetch('/api/solve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, strategy }),
    });
    const data = await resp.json();
    if (data.error) { setStatus(data.error, 'var(--red)'); return; }

    taskId = data.task_id;
    connectWS(taskId);
    setStatus('协作中...');
  } catch (e) {
    setStatus('请求失败: ' + e.message, 'var(--red)');
  }
}

function connectWS(tid) {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = proto + '//' + location.host + '/ws/solve/' + tid;
  ws = new WebSocket(url);

  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    switch (msg.type) {
      case 'token':
        buffers[msg.agent] += msg.content;
        const out = document.getElementById('out-' + msg.agent);
        out.innerHTML = '<p>' + simpleMarkdown(buffers[msg.agent]) + '</p>';
        out.scrollTop = out.scrollHeight;
        const mid = (msg.progress_start + msg.progress_end) / 2 * 100;
        setProgress(msg.agent, Math.min(mid, 95));
        break;
      case 'phase':
        if (msg.status === 'completed') {
          if (msg.result) {
            buffers[msg.agent] = msg.result;
            document.getElementById('out-' + msg.agent).innerHTML =
              '<p>' + simpleMarkdown(msg.result) + '</p>';
          }
          hideSpinner(msg.agent);
          setProgress(msg.agent, 100);
        }
        break;
      case 'done':
        setStatus('✓ 协作完成', 'var(--green)');
        agents.forEach(a => { hideSpinner(a); setProgress(a, 100); });
        ws.close();
        break;
      case 'error':
        setStatus('✗ ' + msg.message, 'var(--red)');
        break;
    }
  };

  ws.onerror = () => setStatus('WebSocket 连接失败', 'var(--red)');
  ws.onclose = () => { if (ws) setStatus('连接已关闭'); };
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

loadSkills();
