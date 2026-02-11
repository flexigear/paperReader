const tabs = document.querySelectorAll('.tab');
const panels = document.querySelectorAll('.panel');
const uploadBtn = document.getElementById('uploadBtn');
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
const updateSummaryBtn = document.getElementById('updateSummaryBtn');

let selectedPaperId = null;
let statusPollTimer = null;

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
  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble';
  bubble.textContent = content;
  if (sourceHint) {
    const source = document.createElement('div');
    source.className = 'chat-source';
    source.textContent = sourceHint;
    bubble.appendChild(source);
  }
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
    const row = document.createElement('div');
    row.className = 'paper-item';

    const openBtn = document.createElement('button');
    openBtn.className = 'paper-open-btn';
    openBtn.type = 'button';
    openBtn.innerHTML = `<span class="paper-title" title="${paper.title}">${paper.title}</span><small>${paper.status}</small>`;
    openBtn.addEventListener('click', () => selectPaper(paper.id));

    const delBtn = document.createElement('button');
    delBtn.className = 'paper-delete-btn';
    delBtn.type = 'button';
    delBtn.textContent = '删除';
    delBtn.addEventListener('click', async () => {
      const ok = window.confirm(`确认删除论文：${paper.title}？`);
      if (!ok) return;
      try {
        await fetchJson(`/api/papers/${paper.id}`, { method: 'DELETE' });
        if (selectedPaperId === paper.id) {
          selectedPaperId = null;
          detail.classList.add('hidden');
          chatBox.innerHTML = '';
          pdfViewer.src = 'about:blank';
          paperTitle.textContent = '论文原文';
        }
        await loadPaperList();
      } catch (error) {
        uploadStatus.textContent = `删除失败：${error.message}`;
      }
    });

    row.appendChild(openBtn);
    row.appendChild(delBtn);
    paperList.appendChild(row);
  });
}

function bindPaperViewer(paperId, title) {
  paperTitle.textContent = title;
  pdfViewer.src = `/api/papers/${paperId}/pdf`;
}

function clearStatusPoll() {
  if (statusPollTimer) {
    clearInterval(statusPollTimer);
    statusPollTimer = null;
  }
}

async function startStatusPoll(paperId) {
  clearStatusPoll();
  statusPollTimer = setInterval(async () => {
    try {
      const paper = await fetchJson(`/api/papers/${paperId}`);
      await loadPaperList();
      uploadStatus.textContent = `解析状态：${paper.status}`;
      if (paper.status === 'completed' || paper.status === 'failed') {
        clearStatusPoll();
        if (paper.status === 'completed') {
          uploadStatus.textContent = `解析完成：${paper.title}`;
          await selectPaper(paperId);
          switchTab('results');
        } else {
          uploadStatus.textContent = `解析失败：${paper.title}`;
        }
      }
    } catch (error) {
      clearStatusPoll();
      uploadStatus.textContent = `轮询失败：${error.message}`;
    }
  }, 2500);
}

async function selectPaper(paperId) {
  selectedPaperId = paperId;
  const paper = await fetchJson(`/api/papers/${paperId}`);

  detail.classList.remove('hidden');
  detailTitle.textContent = `${paper.title} (${paper.status})`;
  setSummary(paper.summary);
  setSummaryMeta(paper.summary_version, paper.summary_updated_at);

  bindPaperViewer(paperId, paper.title);

  chatBox.innerHTML = '';
  const messages = await fetchJson(`/api/papers/${paperId}/chat`);
  messages.forEach((m) => addChatLine(m.role, m.content, m.source_hint));
}

async function uploadSelectedFile(file) {
  if (!file) return;

  clearStatusPoll();
  uploadStatus.textContent = '上传中...';
  const formData = new FormData();
  formData.append('file', file);

  try {
    const result = await fetchJson('/api/papers/upload', {
      method: 'POST',
      body: formData,
    });
    selectedPaperId = result.id;
    bindPaperViewer(result.id, result.title);
    uploadStatus.textContent = result.duplicate
      ? `已过滤重复论文：${result.title}（复用已有结果）`
      : `已上传：${result.title}，正在解析（queued）。`;
    await loadPaperList();
    if (result.status === 'completed') {
      await selectPaper(result.id);
      switchTab('results');
    } else if (result.status === 'queued' || result.status === 'processing') {
      await startStatusPoll(result.id);
    } else {
      uploadStatus.textContent = `上传已接收：${result.title}，状态为 ${result.status}。请稍后查看。`;
    }
  } catch (error) {
    uploadStatus.textContent = `上传失败：${error.message}`;
  } finally {
    pdfInput.value = '';
  }
}

uploadBtn.addEventListener('click', () => {
  pdfInput.click();
});

pdfInput.addEventListener('change', async () => {
  const file = pdfInput.files?.[0];
  await uploadSelectedFile(file);
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
  } catch (error) {
    addChatLine('assistant', `请求失败：${error.message}`);
  }
});

updateSummaryBtn.addEventListener('click', async () => {
  if (!selectedPaperId) return;
  try {
    const paper = await fetchJson(`/api/papers/${selectedPaperId}/update-summary-from-discussion`, {
      method: 'POST',
    });
    setSummary(paper.summary);
    setSummaryMeta(paper.summary_version, paper.summary_updated_at);
  } catch (error) {
    addChatLine('assistant', `更新总结失败：${error.message}`);
  }
});

loadPaperList().catch((err) => {
  uploadStatus.textContent = `初始化失败：${err.message}`;
});
