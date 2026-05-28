let ws = null, taskId = null;

const ROLE_META = {
  modeling: { label: '建模智能体', progressStart: 0.05, progressEnd: 0.3 },
  programming: { label: '编程智能体', progressStart: 0.3, progressEnd: 0.55 },
  writing: { label: '写作智能体', progressStart: 0.55, progressEnd: 0.8 },
  synthesis: { label: '总控整合', progressStart: 0.8, progressEnd: 1.0 },
};
const agents = Object.keys(ROLE_META);
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
  if (!el) return;
  el.textContent = msg;
  el.style.color = color || '';
}

function showSpinner(agent) {
  const spinner = document.getElementById('spin-' + agent);
  const output = document.getElementById('out-' + agent);
  if (spinner) spinner.classList.remove('hidden');
  if (output) output.classList.add('cursor');
}

function hideSpinner(agent) {
  const spinner = document.getElementById('spin-' + agent);
  const output = document.getElementById('out-' + agent);
  if (spinner) spinner.classList.add('hidden');
  if (output) output.classList.remove('cursor');
}

function setProgress(agent, pct) {
  const bar = document.getElementById('bar-' + agent);
  if (bar) bar.style.width = pct + '%';
}

function resetOutputState() {
  const timeline = document.getElementById('loop-timeline');
  if (timeline) {
    timeline.innerHTML =
      '<div class="timeline-empty">协调者会根据上下文动态选择探索、建模、编程、调试、写作、评审或总结。</div>';
  }
  agents.forEach(a => {
    buffers[a] = '';
    const out = document.getElementById('out-' + a);
    if (out) out.innerHTML = '等待协调者调用。';
    setProgress(a, 0);
    showSpinner(a);
  });
  updateArtifactState();
}

function appendTimelineEvent(agent, status) {
  const timeline = document.getElementById('loop-timeline');
  if (!timeline) return;
  const empty = timeline.querySelector('.timeline-empty');
  if (empty) empty.remove();
  const item = document.createElement('div');
  item.className = 'timeline-item' + (status === 'running' ? ' active' : '');
  item.innerHTML =
    '<div class="timeline-role">' + (ROLE_META[agent]?.label || agent) + '</div>' +
    '<div class="timeline-status">' + status + '</div>';
  timeline.appendChild(item);
  timeline.scrollLeft = timeline.scrollWidth;
}

function setRunState(text, color) {
  const el = document.getElementById('run-state');
  if (!el) return;
  el.textContent = text;
  el.style.color = color || '';
}

function updateArtifactState() {
  const hasCode = Boolean(extractCodeFromOutput(buffers.programming));
  const hasLatex = Boolean(extractLatexFromOutput(buffers.writing));
  const hasAny = agents.some(a => buffers[a] && buffers[a].trim());
  const codeButton = document.getElementById('btn-export-code');
  const latexButton = document.getElementById('btn-export-latex');
  const allButton = document.getElementById('btn-download-all');
  if (codeButton) codeButton.disabled = !hasCode;
  if (latexButton) latexButton.disabled = !hasLatex;
  if (allButton) allButton.disabled = !hasAny;
}

async function startSolve() {
  if (!isQuestionReady()) return;
  const question = document.getElementById('question').value.trim();

  const strategy = document.getElementById('strategy').value;
  resetOutputState();
  setRunState('Running');
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
        appendTimelineEvent(msg.agent, 'running');
        buffers[msg.agent] += msg.content;
        const out = document.getElementById('out-' + msg.agent);
        if (out) {
          out.innerHTML = '<p>' + simpleMarkdown(buffers[msg.agent]) + '</p>';
          out.scrollTop = out.scrollHeight;
        }
        const mid = (msg.progress_start + msg.progress_end) / 2 * 100;
        setProgress(msg.agent, Math.min(mid, 95));
        updateArtifactState();
        break;
      case 'phase':
        if (msg.status === 'completed') {
          if (msg.result) {
            buffers[msg.agent] = msg.result;
            const phaseOut = document.getElementById('out-' + msg.agent);
            if (phaseOut) phaseOut.innerHTML = '<p>' + simpleMarkdown(msg.result) + '</p>';
          }
          appendTimelineEvent(msg.agent, 'completed');
          hideSpinner(msg.agent);
          setProgress(msg.agent, 100);
          updateArtifactState();
        }
        break;
      case 'done':
        if (msg.result) {
          const resultMap = {
            modeling: msg.result.modeling || '',
            programming: msg.result.programming || '',
            writing: msg.result.writing || '',
            synthesis: msg.result.synthesis || '',
          };
          agents.forEach(a => {
            if (resultMap[a]) {
              buffers[a] = resultMap[a];
              const doneOut = document.getElementById('out-' + a);
              if (doneOut) doneOut.innerHTML = '<p>' + simpleMarkdown(resultMap[a]) + '</p>';
            }
          });
        }
        setStatus('✓ 协作完成', 'var(--green)');
        setRunState('Complete', 'var(--green)');
        agents.forEach(a => { hideSpinner(a); setProgress(a, 100); });
        updateArtifactState();
        const closing = ws;
        ws = null;
        if (closing) closing.close();
        break;
      case 'error':
        setStatus('✗ ' + msg.message, 'var(--red)');
        setRunState('Error', 'var(--red)');
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
      questionEl.style.border = '2px solid var(--green)';
      setTimeout(function() { questionEl.style.border = ''; }, 2000);
      var details = '✓ ' + data.pages + ' 页, ' + data.full_length + ' 字符';
      if (data.table_count) details += ', ' + data.table_count + ' 个表格';
      if (data.image_count) details += ', ' + data.image_count + ' 张图片';
      if (data.image_described) details += '(' + data.image_described + '张已识别)';
      details += data.truncated ? ' (已截取前12000字)' : '';
      statusEl.textContent = details;
      statusEl.style.color = 'var(--green)';
      setStatus('题目已从PDF提取，点击下方按钮开始分析', 'var(--green)');
    })
    .catch(function(e) {
      statusEl.textContent = '✗ ' + e.message;
      statusEl.style.color = 'var(--red)';
      setStatus('PDF上传失败，请确认服务器已重启且PyMuPDF已安装', 'var(--red)');
    });
  // Reset so same file re-select works
  fileInput.value = '';
}

function isQuestionReady() {
  var q = document.getElementById('question').value.trim();
  if (!q) { setStatus('请先输入问题或上传PDF提取题目', 'var(--red)'); return false; }
  return true;
}

loadSkills();
