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

function runCode() {
  const code = extractCodeFromOutput(buffers['programming']);
  if (!code) { setStatus('未找到可执行代码', 'var(--red)'); return; }
  setStatus('沙箱执行中...');
  fetch('/api/tool/python_exec', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code: code }),
  })
    .then(r => r.json())
    .then(data => {
      const el = document.getElementById('code-result');
      el.classList.remove('hidden');
      el.textContent = data.result || data.error || '执行完成（无输出）';
      setStatus(data.error ? '执行出错' : '执行完成', data.error ? 'var(--red)' : 'var(--green)');
    })
    .catch(e => { setStatus('沙箱请求失败: ' + e.message, 'var(--red)'); });
}

function exportCode() {
  const code = extractCodeFromOutput(buffers['programming']);
  downloadBlob(code || buffers['programming'], 'model_solution.py', 'text/x-python');
}

function compileLatex() {
  const latex = extractLatexFromOutput(buffers['writing']);
  if (!latex) { setStatus('未找到 LaTeX 源码', 'var(--red)'); return; }
  setStatus('LaTeX 编译中...');
  fetch('/api/tool/latex_compile', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tex_content: latex }),
  })
    .then(r => r.json())
    .then(data => {
      const el = document.getElementById('latex-result');
      el.classList.remove('hidden');
      if (data.pdf_url) {
        el.innerHTML = '<a href="' + data.pdf_url + '" target="_blank">📄 查看 PDF</a>';
        setStatus('编译成功', 'var(--green)');
      } else {
        el.textContent = data.error || '编译失败';
        setStatus('编译失败', 'var(--red)');
      }
    })
    .catch(e => { setStatus('编译请求失败: ' + e.message, 'var(--red)'); });
}

function exportLatex() {
  const latex = extractLatexFromOutput(buffers['writing']);
  downloadBlob(latex || buffers['writing'], 'paper.tex', 'text/x-latex');
}

function downloadAll() {
  const zipContent = [
    { name: 'model_solution.py', content: extractCodeFromOutput(buffers['programming']) || buffers['programming'] },
    { name: 'paper.tex', content: extractLatexFromOutput(buffers['writing']) || buffers['writing'] },
    { name: 'synthesis.md', content: buffers['synthesis'] },
    { name: 'modeling_output.md', content: buffers['modeling'] },
  ].filter(f => f.content);

  zipContent.forEach(f => downloadBlob(f.content, f.name));
  setStatus('已导出 ' + zipContent.length + ' 个文件', 'var(--green)');
}

function extractCodeFromOutput(text) {
  if (!text) return '';
  const pyMatch = text.match(/```python\n?([\s\S]*?)```/);
  if (pyMatch) return pyMatch[1].trim();
  const defMatch = text.match(/(?:^|\n)(import\s[\s\S]*?(?:return|print)[\s\S]*?)(?:\n\n|$)/);
  return defMatch ? defMatch[1].trim() : '';
}

function extractLatexFromOutput(text) {
  if (!text) return '';
  const match = text.match(/```latex\n?([\s\S]*?)```/) || text.match(/\\documentclass[\s\S]*?\\end{document}/);
  return match ? (match[1] || match[0]).trim() : '';
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

async function onPDFSelected() {
  const fileInput = document.getElementById('pdf-file');
  const file = fileInput.files[0];
  if (!file) return;

  console.log('[PDF Upload]', file.name, file.size, 'bytes');

  document.getElementById('pdf-name').textContent = file.name;
  const statusEl = document.getElementById('upload-status');
  statusEl.textContent = '提取中...';
  statusEl.style.color = '';

  const formData = new FormData();
  formData.append('file', file);

  try {
    const resp = await fetch('/api/upload/pdf', { method: 'POST', body: formData });
    const data = await resp.json();
    console.log('[PDF Upload] response:', data);
    if (data.error) {
      statusEl.textContent = '✗ ' + data.error;
      statusEl.style.color = 'var(--red)';
      return;
    }
    document.getElementById('question').value = data.text;
    statusEl.textContent =
      '✓ 已提取 ' + data.pages + ' 页, ' + data.full_length + ' 字符' +
      (data.truncated ? ' (已截取前8000字)' : '');
    statusEl.style.color = 'var(--green)';
  } catch (e) {
    console.error('[PDF Upload]', e);
    statusEl.textContent = '上传失败: ' + e.message;
    statusEl.style.color = 'var(--red)';
  }
  // Reset file input so same file can be re-selected
  fileInput.value = '';
}

loadSkills();
