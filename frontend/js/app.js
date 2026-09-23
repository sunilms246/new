/**
 * Frontend JavaScript Application Logic
 * HTTP Error Defect Report Generator (RAG-based)
 */

document.addEventListener('DOMContentLoaded', () => {
  const isFileMode = location.protocol === 'file:';
  const API_BASE = isFileMode ? null : '';

  const defectInput = document.getElementById('defectInput');
  const clearBtn = document.getElementById('clearBtn');
  const generateBtn = document.getElementById('generateBtn');
  const regenerateBtn = document.getElementById('regenerateBtn');
  const samplePills = document.querySelectorAll('.sample-pill');

  const statusBanner = document.getElementById('statusBanner');
  
  const candidatesSection = document.getElementById('candidatesSection');
  const candidatesList = document.getElementById('candidatesList');
  const resultsContainer = document.getElementById('resultsContainer');
  const loadingOverlay = document.getElementById('loadingOverlay');

  // Report Elements
  const httpStatusBadge = document.getElementById('httpStatusBadge');
  const severityBadge = document.getElementById('severityBadge');
  const groundingBadge = document.getElementById('groundingBadge');
  const reportTitle = document.getElementById('reportTitle');
  const reportLikelyCause = document.getElementById('reportLikelyCause');
  const reportSteps = document.getElementById('reportSteps');
  const reportExpected = document.getElementById('reportExpected');
  const reportActual = document.getElementById('reportActual');
  const reportRemediation = document.getElementById('reportRemediation');

  // Transparency Elements
  const latencyBadge = document.getElementById('latencyBadge');
  const transMatchReason = document.getElementById('transMatchReason');
  const transRetrievedChunk = document.getElementById('transRetrievedChunk');
  const transAttribution = document.getElementById('transAttribution');
  const mdnLink = document.getElementById('mdnLink');

  // Action Buttons
  const copyTextBtn = document.getElementById('copyTextBtn');
  const copyMarkdownBtn = document.getElementById('copyMarkdownBtn');
  const copyJiraBtn = document.getElementById('copyJiraBtn');
  const exportJsonBtn = document.getElementById('exportJsonBtn');

  let currentResponseData = null;

  function showBanner(message, kind = 'error') {
    statusBanner.textContent = message;
    statusBanner.className = `status-banner ${kind}`;
  }

  function clearBanner() {
    statusBanner.classList.add('hidden');
  }

  // If opened directly as a file, the backend API cannot be reached.
  // Show an actionable message instead of the generate flow.
  if (isFileMode) {
    showBanner('Backend API not reachable. This app must be served over HTTP. ' +
      'Run: python -m uvicorn app.main:app --reload  and open http://127.0.0.1:8000/', 'warn');
    generateBtn.disabled = true;
  }

  // Clear text
  clearBtn.addEventListener('click', () => {
    defectInput.value = '';
    defectInput.focus();
    candidatesSection.classList.add('hidden');
  });

  // Sample prompt clicks
  samplePills.forEach(pill => {
    pill.addEventListener('click', () => {
      defectInput.value = pill.dataset.text;
      handleGenerate();
    });
  });

  // Generate Button
  generateBtn.addEventListener('click', () => {
    handleGenerate();
  });

  // Regenerate Button (FR7) - reruns with same input, optionally a selected code
  regenerateBtn.addEventListener('click', () => {
    const activeCandidate = document.querySelector('.candidate-item.candidate-active');
    const code = activeCandidate && activeCandidate.dataset.code
      ? Number(activeCandidate.dataset.code)
      : null;
    handleGenerate(code, true);
  });

  // Ctrl+Enter keyboard shortcut
  defectInput.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      handleGenerate();
    }
  });

  // Main Generation Handler
  async function handleGenerate(selectedCode = null) {
    if (isFileMode) return;

    const rawInput = defectInput.value.strip ? defectInput.value.strip() : defectInput.value.trim();
    if (!rawInput) {
      showBanner('Please enter a raw defect description (e.g., "login problem", "404", "getting 500 error").', 'warn');
      defectInput.focus();
      return;
    }

    clearBanner();
    showLoading(true);
    regenerateBtn.classList.remove('hidden');

    try {
      const payload = {
        raw_input: rawInput,
        selected_code: selectedCode
      };

      const response = await fetch(`${API_BASE}/api/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Server returned error');
      }

      const data = await response.json();
      currentResponseData = data;
      renderResults(data);

    } catch (error) {
      console.error('Error generating defect report:', error);
      showBanner('Error generating report: ' + error.message);
    } finally {
      showLoading(false);
    }
  }

  // Render Data into UI
  function renderResults(data) {
    resultsContainer.classList.remove('hidden');

    // Render Candidate Status Codes Pills
    if (data.transparency.candidates && data.transparency.candidates.length > 0) {
      candidatesSection.classList.remove('hidden');
      candidatesList.innerHTML = '';

      data.transparency.candidates.forEach(cand => {
        const item = document.createElement('div');
        const isActive = data.transparency.detected_code === cand.code;
        item.className = `candidate-item ${isActive ? 'candidate-active' : 'candidate-inactive'}`;
        item.dataset.code = cand.code;
        item.innerHTML = `<i class="fa-solid ${isActive ? 'fa-circle-check' : 'fa-circle-dot'}"></i> ${cand.name} (${cand.match_type})`;
        
        item.addEventListener('click', () => {
          if (!isActive) {
            handleGenerate(cand.code);
          }
        });
        candidatesList.appendChild(item);
      });
    } else {
      candidatesSection.classList.add('hidden');
    }

    // Status & Severity Badges
    if (data.transparency.detected_code) {
      httpStatusBadge.textContent = `HTTP ${data.transparency.detected_code}`;
      httpStatusBadge.className = 'status-code-badge';
      if (data.transparency.detected_code >= 500) {
        httpStatusBadge.classList.add('status-code-5xx');
      }
      httpStatusBadge.classList.remove('hidden');
    } else {
      httpStatusBadge.classList.add('hidden');
    }

    const sev = data.suggested_severity.toLowerCase();
    severityBadge.textContent = `${data.suggested_severity} Severity`;
    severityBadge.className = `severity-badge severity-${sev}`;

    if (data.is_http_grounded) {
      groundingBadge.innerHTML = `<i class="fa-solid fa-shield-halved"></i> MDN Grounded`;
      groundingBadge.className = 'grounding-badge';
    } else {
      groundingBadge.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> General QA Defect`;
      groundingBadge.className = 'grounding-badge text-muted';
    }

    // Report Fields
    reportTitle.textContent = data.title;
    reportLikelyCause.textContent = data.likely_cause;

    // Steps list
    reportSteps.innerHTML = '';
    data.steps_to_reproduce.forEach(step => {
      const li = document.createElement('li');
      li.textContent = step;
      reportSteps.appendChild(li);
    });

    reportExpected.textContent = data.expected_result;
    reportActual.textContent = data.actual_result;
    reportRemediation.textContent = data.developer_remediation;

    // Transparency Panel
    latencyBadge.innerHTML = `<i class="fa-solid fa-bolt"></i> ${data.transparency.latency_ms}ms`;
    transMatchReason.textContent = data.transparency.match_reason;
    transRetrievedChunk.textContent = data.transparency.retrieved_chunk;
    transAttribution.textContent = data.transparency.attribution;

    if (data.transparency.mdn_url) {
      mdnLink.href = data.transparency.mdn_url;
      mdnLink.classList.remove('hidden');
    } else {
      mdnLink.classList.add('hidden');
    }

    // Scroll to results smoothly
    resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // Copy / Export Handlers
  copyTextBtn.addEventListener('click', () => {
    if (!currentResponseData) return;
    const stepsText = currentResponseData.steps_to_reproduce.map((s, i) => `${i + 1}. ${s}`).join('\n');
    const text = `DEFECT REPORT: ${currentResponseData.title}
Status Code: ${currentResponseData.transparency.detected_code || 'N/A'}
Severity: ${currentResponseData.suggested_severity} (${currentResponseData.severity_rationale})

LIKELY CAUSE:
${currentResponseData.likely_cause}

STEPS TO REPRODUCE:
${stepsText}

EXPECTED RESULT:
${currentResponseData.expected_result}

ACTUAL RESULT:
${currentResponseData.actual_result}

DEVELOPER REMEDIATION:
${currentResponseData.developer_remediation}

Source Grounding: ${currentResponseData.transparency.attribution}`;
    copyToClipboard(text, copyTextBtn, 'Text Copied!');
  });

  copyMarkdownBtn.addEventListener('click', () => {
    if (!currentResponseData) return;
    const stepsMd = currentResponseData.steps_to_reproduce.map((s, i) => `${i + 1}. ${s}`).join('\n');
    const md = `# ${currentResponseData.title}

**HTTP Status Code:** \`${currentResponseData.transparency.detected_code || 'N/A'}\`
**Suggested Severity:** \`${currentResponseData.suggested_severity}\` (${currentResponseData.severity_rationale})

### 🔍 Likely Cause (MDN Grounded)
${currentResponseData.likely_cause}

### 📋 Steps to Reproduce
${stepsMd}

### 🟢 Expected Result
${currentResponseData.expected_result}

### 🔴 Actual Result
${currentResponseData.actual_result}

### 🛠️ Developer Remediation
${currentResponseData.developer_remediation}

---
*Generated by TCS Tech Day HTTP RAG Defect Tool | Grounding: ${currentResponseData.transparency.attribution}*`;
    copyToClipboard(md, copyMarkdownBtn, 'Markdown Copied!');
  });

  copyJiraBtn.addEventListener('click', () => {
    if (!currentResponseData) return;
    const stepsJira = currentResponseData.steps_to_reproduce.map((s, i) => `# ${s}`).join('\n');
    const jira = `h1. ${currentResponseData.title}
*HTTP Status:* ${currentResponseData.transparency.detected_code || 'N/A'}
*Severity:* ${currentResponseData.suggested_severity}

h3. Likely Cause
${currentResponseData.likely_cause}

h3. Steps to Reproduce
${stepsJira}

h3. Expected Result
${currentResponseData.expected_result}

h3. Actual Result
${currentResponseData.actual_result}

h3. Remediation
${currentResponseData.developer_remediation}`;
    copyToClipboard(jira, copyJiraBtn, 'Jira Format Copied!');
  });

  exportJsonBtn.addEventListener('click', () => {
    if (!currentResponseData) return;
    const jsonStr = JSON.stringify(currentResponseData, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `defect-report-${currentResponseData.transparency.detected_code || 'general'}.json`;
    a.click();
    URL.revokeObjectURL(url);
  });

  function copyToClipboard(text, btnElement, successMsg) {
    navigator.clipboard.writeText(text).then(() => {
      const originalText = btnElement.innerHTML;
      btnElement.innerHTML = `<i class="fa-solid fa-check"></i> ${successMsg}`;
      setTimeout(() => {
        btnElement.innerHTML = originalText;
      }, 2000);
    });
  }

  function showLoading(isLoading) {
    if (isLoading) {
      loadingOverlay.classList.remove('hidden');
    } else {
      loadingOverlay.classList.add('hidden');
    }
  }
});
