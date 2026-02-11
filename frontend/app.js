const tabs = document.querySelectorAll('.tab');
const panels = document.querySelectorAll('.panel');
const uploadForm = document.getElementById('uploadForm');
const pdfInput = document.getElementById('pdfFile');
const uploadStatus = document.getElementById('uploadStatus');
const paperList = document.getElementById('paperList');
const pdfViewer = document.getElementById('pdfViewer');
const paperTitle = document.getElementById('paperTitle');
const detail = document.getElementById('detail');
const detailTitle = document.getElementById('detailTitle');
const summaryMeta = document.getElementById('summaryMeta');
const refreshSummaryBtn = document.getElementById('refreshSummaryBtn');
const chatForm = document.getElementById('chatForm');
const chatInput = document.getElementById('chatInput');
const chatBox = document.getElementById('chatBox');

let selectedPaperId = null;

const summaryFields = {
  zh: {
    question: document.getElementById('zhQuestion'),
    solution: document.getElementById('zhSolution'),
    findings: document.getElementById('zhFindings'),
  },
  en: {
    question: document.getElementById('enQuestion'),
    solution: document.getElementById('enSolution'),
    findings: document.getElementById('enFindings'),
  },
  ja: {
    question: document.getElementById('jaQuestion'),
    solution: document.getElementById('jaSolution'),
    findings: document.getElementById('jaFindings'),
  },
};

function switchTab(targetId) {
  tabs.forEach((tab) => tab.classList.toggle('active', tab.dataset.tab === targetId));
  panels.forEach((panel) => panel.classList.toggle('active', panel.id === targetId));
}

tabs.forEach((tab) => tab.addEventListener('click', () => switchTab(tab.dataset.tab)));

function setSummary(summary) {
  ['zh', 'en', 'ja'].forEach((lang) => {
    const block = summary?.[lang] || {};
    summaryFields[lang].question.textContent = block.question || '-';
    summaryFields[lang].solution.textContent = block.solution || '-';
    summaryFields[lang].findings.textContent = block.findings || '-';
  });
}

function setSummaryMeta(version, updatedAt) {
  if (!version) {
    summaryMeta.textContent = '总结版本：v0（尚未生成）';
    return;
  }
  const timeText = updatedAt ? new Date(updatedAt).toLocaleString() : '-';
  summaryMeta.textContent = `总结版本：v${version}，最近更新：${timeText}`;
}

function addChatLine(role, content, sourceHint = null) {
  const line = document.createElement('div');
  line.className = `chat-line ${role}`;
  const bubble = document.createElement('span');
  bubble.textContent = sourceHint ? `${content}\n(${sourceHint})` : content;
  line.appendChild(bubble);
  chatBox.appendChild(line);
  chatBox.scrollTop = chatBox.scrollHeight;
}

async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

async function loadPaperList() {
  const papers = await fetchJson('/api/papers');
  paperList.innerHTML = '';

  papers.forEach((paper) => {
    const item = document.createElement('button');
    item.className = 'paper-item';
    item.type = 'button';
    item.innerHTML = `<div title="${paper.title}">${paper.title}</div><small>${paper.status}</small>`;
    item.addEventListener('click', () => selectPaper(paper.id));
    paperList.appendChild(item);
  });
}

async function selectPaper(paperId) {
  selectedPaperId = paperId;
  const paper = await fetchJson(`/api/papers/${paperId}`);

  detail.classList.remove('hidden');
  detailTitle.textContent = `${paper.title} (${paper.status})`;
  setSummary(paper.summary);
  setSummaryMeta(paper.summary_version, paper.summary_updated_at);

  paperTitle.textContent = paper.title;
  pdfViewer.src = `/api/papers/${paperId}/pdf`;

  chatBox.innerHTML = '';
  const messages = await fetchJson(`/api/papers/${paperId}/chat`);
  messages.forEach((m) => addChatLine(m.role, m.content, m.source_hint));
}

uploadForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const file = pdfInput.files?.[0];
  if (!file) return;

  uploadStatus.textContent = '上传中...';
  const formData = new FormData();
  formData.append('file', file);

  try {
    const result = await fetchJson('/api/papers/upload', {
      method: 'POST',
      body: formData,
    });
    uploadStatus.textContent = `已上传：${result.title}，正在解析。`;
    await loadPaperList();
    switchTab('results');
  } catch (error) {
    uploadStatus.textContent = `上传失败：${error.message}`;
  }
});

refreshSummaryBtn.addEventListener('click', async () => {
  if (!selectedPaperId) return;
  await fetchJson(`/api/papers/${selectedPaperId}/refresh-summary`, { method: 'POST' });
  await selectPaper(selectedPaperId);
});

chatForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!selectedPaperId || !chatInput.value.trim()) return;

  const message = chatInput.value.trim();
  addChatLine('user', message);
  chatInput.value = '';

  try {
    const data = await fetchJson(`/api/papers/${selectedPaperId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });
    addChatLine('assistant', data.answer.content, data.answer.source_hint);
    setSummary(data.summary);
    setSummaryMeta(data.summary_version, data.summary_updated_at);
  } catch (error) {
    addChatLine('assistant', `请求失败：${error.message}`);
  }
});

loadPaperList().catch((err) => {
  uploadStatus.textContent = `初始化失败：${err.message}`;
});
