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
const detailCloseBtn = document.getElementById('detailCloseBtn');
const summaryMeta = document.getElementById('summaryMeta');
const refreshSummaryBtn = document.getElementById('refreshSummaryBtn');
const chatForm = document.getElementById('chatForm');
const chatInput = document.getElementById('chatInput');
const chatBox = document.getElementById('chatBox');
const updateSummaryBtn = document.getElementById('updateSummaryBtn');
const paperPrevBtn = document.getElementById('paperPrevBtn');
const paperNextBtn = document.getElementById('paperNextBtn');
const paperPageInput = document.getElementById('paperPageInput');
const paperOpenNewBtn = document.getElementById('paperOpenNewBtn');
const paperPageTotal = document.getElementById('paperPageTotal');

let selectedPaperId = null;
let statusPollTimer = null;
let currentPdfPage = 1;
let totalPdfPages = null;

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

function formatSummaryText(raw) {
  const input = typeof raw === 'string' ? raw : '';
  if (!input.trim()) return '-';

  // Keep model semantics intact; only normalize line endings and excessive empty lines.
  const text = input.replace(/\r\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
  return text || '-';
}

function setSummary(summary) {
  ['zh', 'en', 'ja'].forEach((lang) => {
    const block = summary?.[lang] || {};
    summaryFields[lang].question.textContent = formatSummaryText(block.question);
    summaryFields[lang].solution.textContent = formatSummaryText(block.solution);
    summaryFields[lang].findings.textContent = formatSummaryText(block.findings);
  });
}

function setSummaryMeta(version, updatedAt) {
  if (!version) {
    summaryMeta.textContent = 'Summary version: v0 (not generated yet)';
    return;
  }
  const timeText = updatedAt ? new Date(updatedAt).toLocaleString() : '-';
  summaryMeta.textContent = `Summary version: v${version}, last updated: ${timeText}`;
}

function buildPdfPageUrl(paperId, page) {
  const safePage = Number.isFinite(page) && page > 0 ? Math.floor(page) : 1;
  return `/api/papers/${paperId}/pdf/page/${safePage}?t=${Date.now()}`;
}

function buildPdfFullUrl(paperId) {
  return `/api/papers/${paperId}/pdf`;
}

function updatePdfNavState() {
  const hasDoc = !!selectedPaperId;
  const isFirst = currentPdfPage <= 1;
  const hasTotal = Number.isFinite(totalPdfPages) && totalPdfPages > 0;
  const isLast = hasTotal && currentPdfPage >= totalPdfPages;
  paperPrevBtn.disabled = !hasDoc || isFirst;
  paperNextBtn.disabled = !hasDoc || isLast;
}

function setPdfTotalPages(pages) {
  if (Number.isFinite(pages) && pages > 0) {
    totalPdfPages = Math.floor(pages);
    paperPageTotal.textContent = `/ ${totalPdfPages}`;
    paperPageInput.max = String(totalPdfPages);
  } else {
    totalPdfPages = null;
    paperPageTotal.textContent = '/ -';
    paperPageInput.removeAttribute('max');
  }
  updatePdfNavState();
}

function setPdfPage(page) {
  if (!selectedPaperId) return;
  let safePage = Number.isFinite(page) && page > 0 ? Math.floor(page) : currentPdfPage;
  if (Number.isFinite(totalPdfPages) && totalPdfPages > 0) {
    safePage = Math.min(safePage, totalPdfPages);
  }
  if (safePage < 1) safePage = 1;
  currentPdfPage = safePage;
  paperPageInput.value = String(safePage);
  const nextUrl = buildPdfPageUrl(selectedPaperId, safePage);
  if (pdfViewer.src === nextUrl) {
    pdfViewer.src = 'about:blank';
    setTimeout(() => {
      pdfViewer.src = nextUrl;
    }, 0);
  } else {
    pdfViewer.src = nextUrl;
  }
  updatePdfNavState();
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
    delBtn.textContent = 'Delete';
    delBtn.addEventListener('click', async () => {
      const ok = window.confirm(`Delete paper: ${paper.title}?`);
      if (!ok) return;
      try {
        await fetchJson(`/api/papers/${paper.id}`, { method: 'DELETE' });
        if (selectedPaperId === paper.id) {
          selectedPaperId = null;
          detail.classList.add('hidden');
          chatBox.innerHTML = '';
          pdfViewer.src = 'about:blank';
          paperTitle.textContent = 'Paper PDF';
        }
        await loadPaperList();
      } catch (error) {
        uploadStatus.textContent = `Delete failed: ${error.message}`;
      }
    });

    row.appendChild(openBtn);
    row.appendChild(delBtn);
    paperList.appendChild(row);
  });
}

function bindPaperViewer(paperId, title) {
  paperTitle.textContent = title;
  currentPdfPage = 1;
  paperPageInput.value = '1';
  updatePdfNavState();
  const pdfUrl = buildPdfPageUrl(paperId, 1);
  pdfViewer.src = pdfUrl;
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
      uploadStatus.textContent = `Processing status: ${paper.status}`;
      if (paper.status === 'completed' || paper.status === 'failed') {
        clearStatusPoll();
        if (paper.status === 'completed') {
          uploadStatus.textContent = `Completed: ${paper.title}`;
          await selectPaper(paperId);
          switchTab('results');
        } else {
          uploadStatus.textContent = `Failed: ${paper.title}`;
        }
      }
    } catch (error) {
      clearStatusPoll();
      uploadStatus.textContent = `Polling failed: ${error.message}`;
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
  setPdfTotalPages(paper.page_count);
  bindPaperViewer(paperId, paper.title);

  chatBox.innerHTML = '';
  const messages = await fetchJson(`/api/papers/${paperId}/chat`);
  messages.forEach((m) => addChatLine(m.role, m.content, m.source_hint));
}

async function uploadSelectedFile(file) {
  if (!file) return;

  clearStatusPoll();
  uploadStatus.textContent = 'Uploading...';
  setPdfTotalPages(null);
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
      ? `Duplicate detected: ${result.title} (reused existing results)`
      : `Uploaded: ${result.title}, queued for processing.`;
    await loadPaperList();
    if (result.status === 'completed') {
      await selectPaper(result.id);
      switchTab('results');
    } else if (result.status === 'queued' || result.status === 'processing') {
      await startStatusPoll(result.id);
    } else {
      uploadStatus.textContent = `Upload received: ${result.title}, status ${result.status}. Check later.`;
    }
  } catch (error) {
    uploadStatus.textContent = `Upload failed: ${error.message}`;
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

detailCloseBtn.addEventListener('click', () => {
  detail.classList.add('hidden');
});

paperPrevBtn.addEventListener('click', () => {
  setPdfPage(currentPdfPage - 1);
});

paperNextBtn.addEventListener('click', () => {
  setPdfPage(currentPdfPage + 1);
});

paperPageInput.addEventListener('change', () => {
  const nextPage = Number.parseInt(paperPageInput.value, 10);
  setPdfPage(nextPage);
});

paperPageInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    event.preventDefault();
    const nextPage = Number.parseInt(paperPageInput.value, 10);
    setPdfPage(nextPage);
  }
});

paperOpenNewBtn.addEventListener('click', () => {
  if (!selectedPaperId) return;
  const url = buildPdfFullUrl(selectedPaperId);
  window.open(url, '_blank', 'noopener');
});

window.addEventListener('resize', () => {
  if (!selectedPaperId) return;
  setPdfPage(currentPdfPage);
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
    addChatLine('assistant', `Request failed: ${error.message}`);
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
    addChatLine('assistant', `Update summary failed: ${error.message}`);
  }
});

loadPaperList().catch((err) => {
  uploadStatus.textContent = `Initialization failed: ${err.message}`;
});
