/**
 * SAUBHAGYAM Outreach Agent — Web Dashboard Frontend Logic
 * Ledger Edition with Inline Draft Editor, Add Lead, Reply Simulator, & Funnel Analytics
 */

let currentDashboardData = null;
let currentSimulationData = null;
let activeFilter = 'all';
let currentSimDays = 0;
let currentView = 'dashboard';
let hetviLeadsData = [];
let hetviLoaded = false;
let hetviActiveFilter = 'all';
let isSafeDemoMode = true; // Safe Demo Mode ON by default (dry-run, no real emails sent)

// Service options for Hetvi lead activation (sourced from project's known services)
const SERVICE_OPTIONS = [
  'eCommerce Development',
  'Dedicated Developers',
  'ERP Development',
  'Cloud Development',
  'AI & Custom Software Development',
  'Lead Gen / Automation',
  'Mobile App Development',
  'UI/UX Design'
];

// Header Demo Mode Toggle Elements
const elBtnDemoModeToggle = document.getElementById('btnDemoModeToggle');
const elDemoModeLabel = document.getElementById('demoModeLabel');

// DOM Elements - Metrics
const elTotalLeads = document.getElementById('valTotalLeads');
const elTotalSlots = document.getElementById('valTotalSlots');
const elContacted = document.getElementById('valContacted');
const elAwaiting = document.getElementById('valAwaiting');
const elFollowUpsDue = document.getElementById('valFollowUpsDue');
const elReplied = document.getElementById('valReplied');
const elOptOuts = document.getElementById('valOptOuts');

// Funnel Elements
const elFunnelValTargets = document.getElementById('funnelValTargets');
const elFunnelValContacted = document.getElementById('funnelValContacted');
const elFunnelValAwaiting = document.getElementById('funnelValAwaiting');
const elFunnelValReplies = document.getElementById('funnelValReplies');
const elFunnelResponseRate = document.getElementById('funnelResponseRate');

// Main Views & Tables
const elLeadsTableBody = document.getElementById('leadsTableBody');
const elEscalationSection = document.getElementById('escalationSection');
const elEscalationBody = document.getElementById('escalationBody');
const elActivityFeed = document.getElementById('activityFeed');
const elActivityCount = document.getElementById('activityCount');

const elSearchInput = document.getElementById('searchInput');
const elFilterPills = document.querySelectorAll('.filter-pill:not([data-hetvi-filter])');
const elQuickDaysBtns = document.querySelectorAll('.btn-time');
const elTimeSlider = document.getElementById('timeSlider');
const elSliderValueText = document.getElementById('sliderValueText');
const elSimDateText = document.getElementById('simDateText');

const elBtnRefresh = document.getElementById('btnRefresh');
const elBtnCheckReplies = document.getElementById('btnCheckReplies');

// Top Nav Tabs
const elNavTabs = document.querySelectorAll('.nav-tab');
const elViewSections = {
  dashboard: document.getElementById('viewDashboard'),
  hetvi: document.getElementById('viewHetviLeads')
};

// Hetvi Leads DOM Elements & Filters
const elHetviTableBody = document.getElementById('hetviTableBody');
const elHetviStateMsg = document.getElementById('hetviStateMsg');
const elBtnRefreshHetvi = document.getElementById('btnRefreshHetvi');
const elHetviSearchInput = document.getElementById('hetviSearchInput');
const elHetviFilterPills = document.querySelectorAll('[data-hetvi-filter]');
const elCountHetviAll = document.getElementById('countHetviAll');
const elCountHetviBoth = document.getElementById('countHetviBoth');
const elCountHetviEmail = document.getElementById('countHetviEmail');
const elCountHetviPhone = document.getElementById('countHetviPhone');

// Lead Modal (Draft Editor) Elements
const elLeadModal = document.getElementById('leadModal');
const elBtnModalClose = document.getElementById('btnModalClose');
const elBtnModalCloseFooter = document.getElementById('btnModalCloseFooter');
const elModalCompany = document.getElementById('modalCompany');
const elModalContact = document.getElementById('modalContact');
const elModalHook = document.getElementById('modalHook');
const elModalEmailSubject = document.getElementById('modalEmailSubject');
const elModalEmailBody = document.getElementById('modalEmailBody');
const elModalSmsBody = document.getElementById('modalSmsBody');
const elModalWhatsappBody = document.getElementById('modalWhatsappBody');
const elModalHistoryList = document.getElementById('modalHistoryList');
const elTabBtns = document.querySelectorAll('.tab-btn');

// Add Lead Modal Elements
const elAddLeadModal = document.getElementById('addLeadModal');
const elBtnAddLead = document.getElementById('btnAddLead');
const elBtnAddLeadClose = document.getElementById('btnAddLeadClose');
const elBtnAddLeadCancel = document.getElementById('btnAddLeadCancel');
const elBtnSubmitAddLead = document.getElementById('btnSubmitAddLead');

// Simulate Reply Modal Elements
const elSimulateReplyModal = document.getElementById('simulateReplyModal');
const elBtnSimulateReply = document.getElementById('btnSimulateReply');
const elBtnSimReplyClose = document.getElementById('btnSimReplyClose');
const elBtnSimReplyCancel = document.getElementById('btnSimReplyCancel');
const elBtnSubmitSimReply = document.getElementById('btnSubmitSimReply');
const elSimReplyLeadSelect = document.getElementById('simReplyLeadSelect');
const elSimReplyChannelSelect = document.getElementById('simReplyChannelSelect');
const elSimReplyText = document.getElementById('simReplyText');
const elPresetPills = document.querySelectorAll('.preset-pill');

// Daily Report Modal Elements
const elDailyReportModal = document.getElementById('dailyReportModal');
const elBtnDailyReport = document.getElementById('btnDailyReport');
const elBtnDailyReportClose = document.getElementById('btnDailyReportClose');
const elBtnDailyReportCancel = document.getElementById('btnDailyReportCancel');
const elDailyReportContent = document.getElementById('dailyReportContent');
const elDailyReportLoading = document.getElementById('dailyReportLoading');
const elBtnCopyDailyReport = document.getElementById('btnCopyDailyReport');
const elCopyReportBtnText = document.getElementById('copyReportBtnText');

const STORAGE_KEY_GUIDE = 'saubhagyam_guide_collapsed';

// --- INITIALIZATION ---
document.addEventListener('DOMContentLoaded', () => {
  try {
    updateDemoModeUI();
  } catch (err) {
    console.error('updateDemoModeUI error:', err);
  }

  try {
    setupNavigation();
  } catch (err) {
    console.error('setupNavigation error:', err);
  }

  try {
    initGuideBanner();
  } catch (err) {
    console.error('initGuideBanner error:', err);
  }

  try {
    setupEventListeners();
  } catch (err) {
    console.error('setupEventListeners error:', err);
  }

  try {
    setupVoiceAssistant();
  } catch (err) {
    console.error('setupVoiceAssistant error:', err);
  }

  loadDashboardData();
});

function updateDemoModeUI() {
  if (!elBtnDemoModeToggle || !elDemoModeLabel) return;
  if (isSafeDemoMode) {
    elBtnDemoModeToggle.className = 'btn btn-demo-mode is-safe';
    elBtnDemoModeToggle.title = 'Safe Demo Mode ACTIVE (Outreach simulated, no external emails/SMS sent). Click to switch to Live Outbound Mode.';
    elDemoModeLabel.textContent = 'Safe Demo Mode';
  } else {
    elBtnDemoModeToggle.className = 'btn btn-demo-mode is-live';
    elBtnDemoModeToggle.title = 'LIVE OUTBOUND ACTIVE (Real SMTP/Twilio messages will be sent to prospects!). Click to switch to Safe Demo Mode.';
    elDemoModeLabel.textContent = 'Live Outbound';
  }
}

function initGuideBanner() {
  const guideWrapper = document.getElementById('guideWrapper');
  const btnToggleGuide = document.getElementById('btnToggleGuide');
  const guideChevron = document.getElementById('guideChevron');
  if (!guideWrapper || !btnToggleGuide) return;

  const stored = localStorage.getItem(STORAGE_KEY_GUIDE);
  // Default to EXPANDED on first visit (stored === null)
  const isCollapsed = stored === 'true';

  applyGuideState(isCollapsed);

  btnToggleGuide.addEventListener('click', () => {
    const nextState = !guideWrapper.classList.contains('is-collapsed');
    applyGuideState(nextState);
    localStorage.setItem(STORAGE_KEY_GUIDE, nextState.toString());
  });

  function applyGuideState(collapsed) {
    if (collapsed) {
      guideWrapper.classList.add('is-collapsed');
      btnToggleGuide.setAttribute('aria-expanded', 'false');
      if (guideChevron) guideChevron.textContent = 'Show';
    } else {
      guideWrapper.classList.remove('is-collapsed');
      btnToggleGuide.setAttribute('aria-expanded', 'true');
      if (guideChevron) guideChevron.textContent = 'Hide';
    }
  }
}

function setupNavigation() {
  elNavTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const targetView = tab.getAttribute('data-view');
      switchView(targetView);
    });
  });
}

function switchView(viewName) {
  if (!elViewSections[viewName]) return;
  currentView = viewName;

  elNavTabs.forEach(t => {
    if (t.getAttribute('data-view') === viewName) {
      t.classList.add('active');
    } else {
      t.classList.remove('active');
    }
  });

  Object.keys(elViewSections).forEach(v => {
    if (v === viewName) {
      elViewSections[v].style.display = 'flex';
    } else {
      elViewSections[v].style.display = 'none';
    }
  });

  // Auto-load Hetvi leads when tab is first switched to
  if (viewName === 'hetvi' && !hetviLoaded) {
    loadHetviLeads();
  }
}

function setupEventListeners() {
  // Safe Demo Mode Toggle
  if (elBtnDemoModeToggle) {
    elBtnDemoModeToggle.addEventListener('click', () => {
      if (isSafeDemoMode) {
        // About to go LIVE — require confirmation
        const confirmed = confirm(
          "WARNING: This will enable LIVE OUTBOUND mode.\n\n" +
          "Real emails/SMS/WhatsApp messages will be sent to real leads " +
          "when you click Send. Are you sure you want to continue?"
        );
        if (!confirmed) return; // stay in Safe Demo Mode, no change
      }
      isSafeDemoMode = !isSafeDemoMode;
      updateDemoModeUI();
      if (isSafeDemoMode) {
        showToast('Safe Demo Mode enabled — outreach actions will be simulated safely.', 'info');
      } else {
        showToast('WARNING: Live Outbound Mode enabled — real messages will be sent!', 'error');
      }
    });
  }

  // 1-Click Smooth Reset Demo
  const elBtnResetDb = document.getElementById('btnResetDb');
  if (elBtnResetDb) {
    elBtnResetDb.addEventListener('click', async () => {
      showToast('Resetting demo to Day 0...', 'info');
      try {
        const res = await fetch('/api/reset-db', { method: 'POST' });
        const data = await res.json();
        showToast('Demo reset to Day 0. All leads ready for fresh outreach.', 'success');
        
        if (elTimeSlider) elTimeSlider.value = 0;
        elQuickDaysBtns.forEach(b => {
          if (b.getAttribute('data-days') === '0') b.classList.add('active');
          else b.classList.remove('active');
        });
        currentSimDays = 0;
        currentSimulationData = null;
        if (elSliderValueText) elSliderValueText.textContent = '+0 days';
        if (elSimDateText) elSimDateText.textContent = 'Today (Real Time)';

        await loadDashboardData();
      } catch (err) {
        showToast('Failed to reset demo: ' + err.message, 'error');
      }
    });
  }

  // Refresh button (if present)
  if (elBtnRefresh) {
    elBtnRefresh.addEventListener('click', () => {
      showToast('Refreshing live data from SQLite...', 'info');
      loadDashboardData();
    });
  }

  // Check Replies
  if (elBtnCheckReplies) {
    elBtnCheckReplies.addEventListener('click', handleCheckReplies);
  }

  // Search input
  if (elSearchInput) {
    elSearchInput.addEventListener('input', () => {
      renderTable();
    });
  }

  // Filter Pills
  elFilterPills.forEach(pill => {
    pill.addEventListener('click', () => {
      elFilterPills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      activeFilter = pill.getAttribute('data-filter');
      renderTable();
    });
  });

  // 4-Step Cadence Timeline Buttons
  elQuickDaysBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      elQuickDaysBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const days = parseInt(btn.getAttribute('data-days'), 10);
      if (elTimeSlider) elTimeSlider.value = days;
      handleTimeTravel(days);
    });
  });

  // Slider Time Travel
  if (elTimeSlider) {
    elTimeSlider.addEventListener('input', (e) => {
      const days = parseInt(e.target.value, 10);
      elQuickDaysBtns.forEach(b => {
        if (parseInt(b.getAttribute('data-days'), 10) === days) {
          b.classList.add('active');
        } else {
          b.classList.remove('active');
        }
      });
      handleTimeTravel(days);
    });
  }

  // Draft Modal Close
  if (elBtnModalClose) elBtnModalClose.addEventListener('click', closeLeadModal);
  if (elBtnModalCloseFooter) elBtnModalCloseFooter.addEventListener('click', closeLeadModal);
  if (elLeadModal) {
    elLeadModal.addEventListener('click', (e) => {
      if (e.target === elLeadModal) closeLeadModal();
    });
  }

  // Modal Tabs
  elTabBtns.forEach(tab => {
    tab.addEventListener('click', () => {
      elTabBtns.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const targetTab = tab.getAttribute('data-tab');

      const pEmail = document.getElementById('tabEmail');
      const pSms = document.getElementById('tabSms');
      const pWa = document.getElementById('tabWhatsapp');
      const pTime = document.getElementById('tabTimeline');
      const pHist = document.getElementById('tabHistory');

      if (pEmail) pEmail.style.display = targetTab === 'email' ? 'block' : 'none';
      if (pSms) pSms.style.display = targetTab === 'sms' ? 'block' : 'none';
      if (pWa) pWa.style.display = targetTab === 'whatsapp' ? 'block' : 'none';
      if (pTime) pTime.style.display = targetTab === 'timeline' ? 'block' : 'none';
      if (pHist) pHist.style.display = targetTab === 'history' ? 'block' : 'none';

      const bEmail = document.getElementById('btnModalSendEmail');
      const bSms = document.getElementById('btnModalSendSms');
      const bWa = document.getElementById('btnModalSendWhatsapp');
      if (bEmail) bEmail.style.display = targetTab === 'email' ? 'inline-block' : 'none';
      if (bSms) bSms.style.display = targetTab === 'sms' ? 'inline-block' : 'none';
      if (bWa) bWa.style.display = targetTab === 'whatsapp' ? 'inline-block' : 'none';
    });
  });

  // --- HETVI LEADS TOOLBAR & REFRESH ---
  if (elBtnRefreshHetvi) {
    elBtnRefreshHetvi.addEventListener('click', () => {
      loadHetviLeads();
    });
  }

  if (elHetviSearchInput) {
    elHetviSearchInput.addEventListener('input', () => {
      renderHetviTable();
    });
  }

  elHetviFilterPills.forEach(pill => {
    pill.addEventListener('click', () => {
      elHetviFilterPills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      hetviActiveFilter = pill.getAttribute('data-hetvi-filter') || 'all';
      renderHetviTable();
    });
  });

  // --- ADD LEAD MODAL (Feature 2) ---
  if (elBtnAddLead) {
    elBtnAddLead.addEventListener('click', () => {
      openAddLeadModal();
    });
  }
  if (elBtnAddLeadClose) elBtnAddLeadClose.addEventListener('click', closeAddLeadModal);
  if (elBtnAddLeadCancel) elBtnAddLeadCancel.addEventListener('click', closeAddLeadModal);
  if (elAddLeadModal) {
    elAddLeadModal.addEventListener('click', (e) => {
      if (e.target === elAddLeadModal) closeAddLeadModal();
    });
  }

  if (elBtnSubmitAddLead) {
    elBtnSubmitAddLead.addEventListener('click', (e) => {
      e.preventDefault();
      submitAddLead(false);
    });
  }
  const btnAddAnyway = document.getElementById('btnAddAnyway');
  if (btnAddAnyway) {
    btnAddAnyway.addEventListener('click', (e) => {
      e.preventDefault();
      submitAddLead(true);
    });
  }
  const btnDismissDuplicate = document.getElementById('btnDismissDuplicate');
  if (btnDismissDuplicate) {
    btnDismissDuplicate.addEventListener('click', (e) => {
      e.preventDefault();
      const banner = document.getElementById('addLeadDuplicateBanner');
      if (banner) banner.style.display = 'none';
    });
  }

  // --- SIMULATE REPLY MODAL (Feature 3) ---
  if (elBtnSimulateReply) {
    elBtnSimulateReply.addEventListener('click', () => {
      // Populate lead options
      if (currentDashboardData && currentDashboardData.leads) {
        elSimReplyLeadSelect.innerHTML = currentDashboardData.leads.map(l => `
          <option value="${l.lead_id}">${l.company} (${l.contact_name})</option>
        `).join('');
      }
      elSimulateReplyModal.style.display = 'flex';
    });
  }
  if (elBtnSimReplyClose) elBtnSimReplyClose.addEventListener('click', closeSimReplyModal);
  if (elBtnSimReplyCancel) elBtnSimReplyCancel.addEventListener('click', closeSimReplyModal);
  if (elSimulateReplyModal) {
    elSimulateReplyModal.addEventListener('click', (e) => {
      if (e.target === elSimulateReplyModal) closeSimReplyModal();
    });
  }

  // Preset pills
  elPresetPills.forEach(pill => {
    pill.addEventListener('click', () => {
      elPresetPills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      elSimReplyText.value = pill.getAttribute('data-text');
    });
  });

  if (elBtnSubmitSimReply) {
    elBtnSubmitSimReply.addEventListener('click', async () => {
      const leadId = elSimReplyLeadSelect.value;
      const channel = elSimReplyChannelSelect.value;
      const replyText = elSimReplyText.value.trim();

      if (!leadId || !replyText) {
        showToast('Please select a lead and enter reply text', 'error');
        return;
      }

      showToast('Processing inbound reply classification...', 'info');

      try {
        const res = await fetch('/api/simulate-reply', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            lead_id: leadId,
            channel: channel,
            reply_text: replyText
          })
        });

        const data = await res.json();
        if (data.status === 'success') {
          playEscalationChime();
          showToast(`Intent: ${data.classification} — Escalation triggered & follow-up halted.`, 'success');
          closeSimReplyModal();
          await loadDashboardData();
        } else {
          showToast(`Error: ${data.message}`, 'error');
        }
      } catch (err) {
        showToast('Failed to simulate reply: ' + err.message, 'error');
      }
    });
  }

  // --- DAILY REPORT MODAL ---
  if (elBtnDailyReport) {
    elBtnDailyReport.addEventListener('click', openDailyReportModal);
  }
  if (elBtnDailyReportClose) elBtnDailyReportClose.addEventListener('click', closeDailyReportModal);
  if (elBtnDailyReportCancel) elBtnDailyReportCancel.addEventListener('click', closeDailyReportModal);
  if (elDailyReportModal) {
    elDailyReportModal.addEventListener('click', (e) => {
      if (e.target === elDailyReportModal) closeDailyReportModal();
    });
  }
  if (elBtnCopyDailyReport) {
    elBtnCopyDailyReport.addEventListener('click', copyDailyReportToClipboard);
  }
}

function openAddLeadModal(prefillData = null) {
  // Reset all form fields
  const elNewCompany = document.getElementById('newCompany');
  const elNewContact = document.getElementById('newContact');
  const elNewRole = document.getElementById('newRole');
  const elNewService = document.getElementById('newService');
  const elNewHook = document.getElementById('newHook');
  const elNewEmail = document.getElementById('newEmail');
  const elNewPhone = document.getElementById('newPhone');

  if (elNewCompany) elNewCompany.value = '';
  if (elNewContact) elNewContact.value = '';
  if (elNewRole) elNewRole.value = '';
  if (elNewService) elNewService.value = '';
  if (elNewHook) elNewHook.value = '';
  if (elNewEmail) elNewEmail.value = '';
  if (elNewPhone) elNewPhone.value = '';

  // Pre-fill if data provided (e.g. from Hetvi activation)
  if (prefillData) {
    if (elNewCompany) elNewCompany.value = prefillData.company || '';
    if (elNewContact) elNewContact.value = prefillData.contact_name || '';
    if (elNewHook) elNewHook.value = prefillData.personalization_hook || '';
    if (elNewEmail) elNewEmail.value = prefillData.email || '';
    if (elNewPhone) elNewPhone.value = prefillData.phone || '';
    if (elNewService && prefillData.primary_service) elNewService.value = prefillData.primary_service;
  }

  const dupBanner = document.getElementById('addLeadDuplicateBanner');
  if (dupBanner) dupBanner.style.display = 'none';

  if (elAddLeadModal) elAddLeadModal.style.display = 'flex';
}

function closeAddLeadModal() {
  if (elAddLeadModal) elAddLeadModal.style.display = 'none';
  const dupBanner = document.getElementById('addLeadDuplicateBanner');
  if (dupBanner) dupBanner.style.display = 'none';
}

async function submitAddLead(force = false) {
  const company = document.getElementById('newCompany').value.trim();
  const contact = document.getElementById('newContact').value.trim();
  const role = document.getElementById('newRole').value.trim();
  const service = document.getElementById('newService').value.trim();
  const hook = document.getElementById('newHook').value.trim();
  const email = document.getElementById('newEmail').value.trim();
  const phone = document.getElementById('newPhone').value.trim();
  const city = (document.getElementById('newCity')?.value || '').trim();
  const industry = (document.getElementById('newIndustry')?.value || '').trim();
  const rawOppVal = (document.getElementById('newOppValue')?.value || '').trim();
  const salesperson = (document.getElementById('newSalesperson')?.value || '').trim();
  const notes = (document.getElementById('newNotes')?.value || '').trim();

  if (!company || !contact) {
    showToast('Please enter Company Name and Decision Maker name', 'error');
    return;
  }

  // Email/phone basic format check
  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!email && !phone) {
    showToast('Enter at least an email or a phone number', 'error');
    return;
  }
  if (email && !emailPattern.test(email)) {
    showToast('Please enter a valid email address', 'error');
    return;
  }

  let oppValue = null;
  if (rawOppVal !== '') {
    const parsed = Number(rawOppVal);
    if (isNaN(parsed) || parsed < 0) {
      showToast('Opportunity value must be a valid positive number', 'error');
      return;
    }
    oppValue = parsed;
  }

  showToast(force ? 'Overriding duplicate check and adding lead...' : 'Adding new target lead & generating AI drafts...', 'info');

  try {
    const res = await fetch('/api/add-lead', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company,
        contact_name: contact,
        designation: role,
        primary_service: service,
        personalization_hook: hook,
        email: email,
        phone: phone,
        city: city || null,
        industry: industry || null,
        opportunity_value: oppValue,
        salesperson: salesperson || null,
        notes: notes || null,
        force: force
      })
    });

    const data = await res.json();
    if (res.status === 409) {
      const banner = document.getElementById('addLeadDuplicateBanner');
      const msg = document.getElementById('addLeadDuplicateMsg');
      if (banner && msg) {
        msg.textContent = data.message || 'Possible duplicate lead detected.';
        banner.style.display = 'block';
        banner.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
      showToast(data.message || 'Duplicate lead detected', 'warning');
      return;
    }

    if (data.status === 'success') {
      showToast(`Added ${contact} (${company}) successfully. AI drafts ready.`, 'success');
      closeAddLeadModal();
      document.getElementById('newCompany').value = '';
      document.getElementById('newContact').value = '';
      if (document.getElementById('newEmail')) document.getElementById('newEmail').value = '';
      if (document.getElementById('newPhone')) document.getElementById('newPhone').value = '';
      await loadDashboardData();
    } else {
      showToast(`Error: ${data.message}`, 'error');
    }
  } catch (err) {
    showToast('Failed to add lead: ' + err.message, 'error');
  }
}

// --- DAILY REPORT MODAL FUNCTIONS ---
async function openDailyReportModal() {
  if (!elDailyReportModal) return;
  elDailyReportModal.style.display = 'flex';
  if (elDailyReportLoading) elDailyReportLoading.style.display = 'block';
  if (elDailyReportContent) {
    elDailyReportContent.style.display = 'none';
    elDailyReportContent.textContent = '';
  }

  try {
    const res = await fetch('/api/daily-report');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const reportText = data.report || data.text || '';
    if (elDailyReportContent) {
      elDailyReportContent.textContent = reportText;
      elDailyReportContent.style.display = 'block';
    }
  } catch (err) {
    if (elDailyReportContent) {
      elDailyReportContent.textContent = `Failed to load daily report: ${err.message}`;
      elDailyReportContent.style.display = 'block';
    }
  } finally {
    if (elDailyReportLoading) elDailyReportLoading.style.display = 'none';
  }
}

function closeDailyReportModal() {
  if (!elDailyReportModal) return;
  elDailyReportModal.style.display = 'none';
}

function copyDailyReportToClipboard() {
  if (!elDailyReportContent) return;
  const text = elDailyReportContent.textContent;
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    if (elCopyReportBtnText) {
      const orig = elCopyReportBtnText.textContent;
      elCopyReportBtnText.textContent = 'Copied!';
      setTimeout(() => {
        elCopyReportBtnText.textContent = orig;
      }, 2000);
    }
    showToast('Report copied to clipboard!', 'success');
  }).catch(err => {
    showToast('Could not copy report: ' + err.message, 'error');
  });
}

function closeSimReplyModal() {
  if (elSimulateReplyModal) elSimulateReplyModal.style.display = 'none';
}

// --- DATA FETCHING ---

async function loadDashboardData() {
  // Show loading indicator in main table and channel tables
  const loadingHtml = '<tr><td colspan="8" class="loading-row"><span class="spinner-inline"></span> Loading outreach database...</td></tr>';
  elLeadsTableBody.innerHTML = loadingHtml;

  try {
    const res = await fetch('/api/dashboard');
    if (!res.ok) throw new Error('Failed to fetch dashboard');
    const data = await res.json();
    currentDashboardData = data;

    // If simulating, fetch fresh simulation
    if (currentSimDays > 0) {
      await handleTimeTravel(currentSimDays);
    } else {
      updateMetrics(data.metrics);
      renderEscalations(data.escalations);
      renderTable();
      renderActivityFeed(data.recent_messages);
    }
  } catch (err) {
    console.error(err);
    elLeadsTableBody.innerHTML = '<tr><td colspan="8" class="loading-row">Failed to load data. Click Refresh to retry.</td></tr>';
    showToast('Failed to load dashboard data', 'error');
  }
}

async function handleTimeTravel(days) {
  currentSimDays = days;
  if (elSliderValueText) elSliderValueText.textContent = `+${days} days`;

  if (days === 0) {
    currentSimulationData = null;
    if (elSimDateText) elSimDateText.textContent = 'Today (Real Time)';
    updateMetrics(currentDashboardData.metrics);
    renderTable();
    return;
  }

  try {
    const res = await fetch(`/api/simulate?days=${days}`);
    const data = await res.json();
    currentSimulationData = data;
    if (elSimDateText) elSimDateText.textContent = `${data.simulated_date} (+${days}d)`;

    const dueCount = data.projections.filter(p => p.projected_action === 'SEND_FOLLOW_UP').length;
    setMetricCardValue(elFollowUpsDue, dueCount);
    document.getElementById('valFollowUpSub').textContent = `Projected due in +${days}d`;

    renderTable();
    showToast(`Time-travel simulated to ${data.simulated_date} (+${days}d)`, 'info');
  } catch (err) {
    console.error(err);
  }
}

function playEscalationChime() {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const now = ctx.currentTime;

    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.type = 'sine';
    osc1.frequency.setValueAtTime(587.33, now);
    gain1.gain.setValueAtTime(0.2, now);
    gain1.gain.exponentialRampToValueAtTime(0.01, now + 0.18);
    osc1.connect(gain1);
    gain1.connect(ctx.destination);
    osc1.start(now);
    osc1.stop(now + 0.18);

    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.type = 'sine';
    osc2.frequency.setValueAtTime(880, now + 0.18);
    gain2.gain.setValueAtTime(0.25, now + 0.18);
    gain2.gain.exponentialRampToValueAtTime(0.01, now + 0.45);
    osc2.connect(gain2);
    gain2.connect(ctx.destination);
    osc2.start(now + 0.18);
    osc2.stop(now + 0.45);
  } catch (e) {}
}

async function handleCheckReplies() {
  const originalText = elBtnCheckReplies.innerHTML;
  elBtnCheckReplies.innerHTML = '<span class="spinner-inline"></span> Scanning…';
  elBtnCheckReplies.disabled = true;

  try {
    const res = await fetch('/api/check-replies', { method: 'POST' });
    const data = await res.json();

    if (data.status === 'success') {
      if (data.replies_found > 0) {
        showToast(`Detected ${data.replies_found} new lead reply(ies).`, 'success');
      } else {
        showToast('Inbox scanned — no new lead replies detected.', 'info');
      }

      if (data.escalations_triggered && data.escalations_triggered.length > 0) {
        playEscalationChime();
        data.escalations_triggered.forEach(esc => {
          showToast(`HOT LEAD ALERT: ${esc.company} (${esc.contact_name}) — ${esc.classification}! Salesperson notified.`, 'error');
        });
      }

      loadDashboardData();
    } else {
      showToast(data.message || 'Error scanning replies', 'error');
    }
  } catch (err) {
    showToast('Failed to trigger reply scan: ' + err.message, 'error');
  } finally {
    elBtnCheckReplies.innerHTML = originalText;
    elBtnCheckReplies.disabled = false;
  }
}

// --- RENDERING ---

function setMetricCardValue(el, val) {
  if (!el) return;
  el.textContent = val;
  const num = parseInt(val, 10);
  if (num === 0 || val === 0 || val === '0') {
    el.classList.add('is-zero');
  } else {
    el.classList.remove('is-zero');
  }
}

function updateMetrics(metrics) {
  if (!metrics) return;
  setMetricCardValue(elTotalLeads, metrics.total_leads);
  elTotalSlots.textContent = `${metrics.total_slots} Channel touchpoints`;
  setMetricCardValue(elContacted, metrics.contacted);
  setMetricCardValue(elAwaiting, metrics.awaiting_reply);
  setMetricCardValue(elFollowUpsDue, metrics.follow_up_due);
  setMetricCardValue(elReplied, metrics.replied);
  setMetricCardValue(elOptOuts, metrics.opted_out);
  document.getElementById('valFollowUpSub').textContent = 'Ready for cadence';

  // Feature 4: Conversion Funnel Bar
  if (elFunnelValTargets) setMetricCardValue(elFunnelValTargets, metrics.total_leads);
  if (elFunnelValContacted) setMetricCardValue(elFunnelValContacted, metrics.contacted);
  if (elFunnelValAwaiting) setMetricCardValue(elFunnelValAwaiting, metrics.awaiting_reply);
  if (elFunnelValReplies) setMetricCardValue(elFunnelValReplies, metrics.replied);
  
  if (elFunnelResponseRate) {
    const rate = metrics.contacted > 0 ? Math.round((metrics.replied / metrics.contacted) * 100) : 0;
    elFunnelResponseRate.textContent = `Response Rate: ${rate}%`;
  }
}

function renderEscalations(escalations) {
  if (!escalations || escalations.length === 0) {
    elEscalationSection.style.display = 'none';
    return;
  }

  elEscalationSection.style.display = 'block';
  const html = escalations.map(e => `
    <div class="escalation-row">
      <strong>${escapeHtml(e.company)} (${escapeHtml(e.contact_name)})</strong> replied on <em>${e.channel.toUpperCase()}</em>:
      <span class="score-badge score-high">${escapeHtml(e.classification)}</span>
      <p style="margin-top: 4px; font-size: 0.8rem; color: var(--color-ink-muted);">
        Recommended Action: Human salesperson to reach out within 24 hours to schedule meeting.
      </p>
    </div>
  `).join('<hr style="border-color: var(--color-border); margin: 8px 0;">');

  elEscalationBody.innerHTML = html;
}

function renderTable() {
  if (!currentDashboardData || !currentDashboardData.leads) return;

  const searchQuery = elSearchInput.value.toLowerCase().trim();
  const leads = currentDashboardData.leads;

  let projMap = {};
  if (currentSimulationData && currentSimulationData.projections) {
    currentSimulationData.projections.forEach(p => {
      projMap[`${p.lead_id}_${p.channel.toLowerCase()}`] = p.projected_action;
    });
  }

  let filteredLeads = leads.filter(lead => {
    const matchSearch = !searchQuery || 
      (lead.company && lead.company.toLowerCase().includes(searchQuery)) ||
      (lead.contact_name && lead.contact_name.toLowerCase().includes(searchQuery)) ||
      (lead.primary_service && lead.primary_service.toLowerCase().includes(searchQuery));

    if (!matchSearch) return false;

    if (activeFilter === 'all') return true;
    
    for (const chKey in lead.channels) {
      const chStatus = currentSimulationData ? 
        projMap[`${lead.lead_id}_${chKey}`] : lead.channels[chKey].status;
      if (chStatus === activeFilter) return true;
    }
    return false;
  });

  // Priority Sort: Leads with BOTH email & phone -> top, ONE available -> middle, NEITHER -> bottom
  filteredLeads.sort((a, b) => getContactPriority(b) - getContactPriority(a));

  if (filteredLeads.length === 0) {
    elLeadsTableBody.innerHTML = `
      <tr>
        <td colspan="8" style="text-align: center; padding: 2rem; color: var(--color-ink-muted);">
          No leads matching your current search or filter criteria.
        </td>
      </tr>
    `;
    return;
  }

  const rowsHtml = filteredLeads.map(lead => {
    let scoreClass = 'score-med';
    const scoreVal = parseInt(lead.lead_score, 10);
    if (isNaN(scoreVal)) {
      scoreClass = 'score-none';
    } else if (scoreVal >= 85) {
      scoreClass = 'score-high';
    } else if (scoreVal < 70) {
      scoreClass = 'score-low';
    }

    const isNewLead = (lead.lead_status === 'NEW');
    const statusBadgeHtml = isNewLead
      ? `<span class="lead-badge-new" title="Unreviewed lead — review & qualify to start outreach">NEW</span>`
      : '';

    return `
      <tr class="${isNewLead ? 'lead-row-new' : ''}">
        <td>
          <div class="company-cell">
            <div class="company-name">
              ${escapeHtml(lead.company)}
              ${statusBadgeHtml}
            </div>
            <div class="company-hook" title="${escapeHtml(lead.personalization_hook || '')}">
              "${escapeHtml(lead.personalization_hook || '—')}"
            </div>
          </div>
        </td>
        <td>
          <div class="contact-name">${escapeHtml(lead.contact_name)}</div>
          <div class="contact-role">${escapeHtml(lead.designation || 'Executive')} • ${escapeHtml(lead.country || 'Global')}</div>
          ${lead.salesperson ? `
            <div class="lead-salesperson-badge" title="Salesperson: ${escapeHtml(lead.salesperson)}">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: middle; margin-right: 3px;"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
              ${escapeHtml(lead.salesperson)}
            </div>
          ` : ''}
        </td>
        <td>
          <span class="score-badge ${scoreClass}">${lead.lead_score ? escapeHtml(lead.lead_score) : '—'}</span>
        </td>
        <td>
          <span class="service-tag ${!lead.primary_service ? 'service-tag-empty' : ''}">${lead.primary_service ? escapeHtml(lead.primary_service) : 'Unspecified'}</span>
        </td>
        <td>
          ${renderChannelPill(lead, 'email', projMap)}
        </td>
        <td>
          ${renderChannelPill(lead, 'sms', projMap)}
        </td>
        <td>
          ${renderChannelPill(lead, 'whatsapp', projMap)}
        </td>
        <td>
          <button class="btn btn-primary btn-sm btn-review-draft" onclick="openLeadModal('${lead.lead_id}')" title="Preview, edit, or customize AI drafts">
            <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M11 2a2 2 0 0 1 2.83 2.83L4.5 14.17 1 15l.83-3.5L11 2z"></path></svg>
            <span>Review & Edit</span>
          </button>
        </td>
      </tr>
    `;
  }).join('');

  elLeadsTableBody.innerHTML = rowsHtml;
}

function renderChannelPill(lead, channelKey, projMap) {
  if (lead.lead_status === 'NEW') {
    return `
      <div class="status-tag status-tag-unreviewed" title="Unreviewed lead (NEW). Review and qualify before outreach.">
        <span class="status-icon" style="font-size: 0.72rem;">⏸</span>
        <div class="status-tag-info">
          <span class="status-tag-title" style="color: var(--text-muted);">Unreviewed</span>
        </div>
      </div>
    `;
  }

  const chData = lead.channels[channelKey] || {};
  let status = chData.status || 'NOT_CONTACTED';
  let meta = '';

  if (currentSimulationData) {
    const proj = projMap[`${lead.lead_id}_${channelKey}`];
    if (proj) {
      status = proj;
    }
  } else {
    if (status === 'AWAITING_REPLY' && chData.next_follow_up && chData.next_follow_up !== '—') {
      meta = `F/U ${chData.next_follow_up}`;
    } else if (status === 'REPLIED' && chData.reply_classification) {
      meta = chData.reply_classification;
    } else if (chData.last_sent && chData.last_sent !== '—') {
      meta = `Sent ${chData.last_sent}`;
    }
  }

  const isInitial = (status === 'SEND_INITIAL' || status === 'NOT_CONTACTED');
  const isFollowUp = (status === 'SEND_FOLLOW_UP' || status === 'FOLLOW_UP_DUE');

  if (isInitial) {
    return `
      <button class="btn-channel-action btn-channel-initial" onclick="triggerDashboardSend('${lead.lead_id}', '${channelKey}', '${escapeHtml(lead.contact_name)}', '${status}')" title="Click to Send Initial ${channelKey.toUpperCase()} now">
        <svg class="btn-icon-send" width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="15" y1="1" x2="8" y2="8"></line><polygon points="15 1 10 15 8 8 1 6 15 1"></polygon></svg>
        <span>Send Initial</span>
      </button>
    `;
  }

  if (isFollowUp) {
    return `
      <button class="btn-channel-action btn-channel-followup" onclick="triggerDashboardSend('${lead.lead_id}', '${channelKey}', '${escapeHtml(lead.contact_name)}', '${status}')" title="Click to Dispatch Follow-Up ${channelKey.toUpperCase()} now">
        <svg class="btn-icon-send" width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>
        <span>Send Follow-Up</span>
      </button>
    `;
  }

  // Passive Status Badges
  if (status === 'AWAITING_REPLY') {
    return `
      <div class="status-tag status-tag-awaiting" title="Outreach sent. Waiting for prospect response.">
        <span class="status-icon">⏳</span>
        <div class="status-tag-info">
          <span class="status-tag-title">Waiting for Reply</span>
          ${meta ? `<span class="status-tag-meta">${meta}</span>` : ''}
        </div>
      </div>
    `;
  }

  if (status === 'REPLIED' || status === 'STOPPED_REPLIED') {
    return `
      <div class="status-tag status-tag-replied" title="Lead responded! Cadence stopped.">
        <span class="status-icon">✓</span>
        <div class="status-tag-info">
          <span class="status-tag-title">Lead Replied</span>
          ${meta ? `<span class="status-tag-meta">${meta}</span>` : ''}
        </div>
      </div>
    `;
  }

  if (status === 'OPTED_OUT') {
    return `
      <div class="status-tag status-tag-optout" title="Lead opted out. Communications suppressed.">
        <span class="status-icon">🛑</span>
        <div class="status-tag-info">
          <span class="status-tag-title">Opted Out</span>
        </div>
      </div>
    `;
  }

  return `
    <div class="status-tag status-tag-neutral">
      <span class="status-tag-title">${formatStatusLabel(status)}</span>
    </div>
  `;
}



window.triggerDashboardSend = async function(leadId, channel, contactName, status, subject = null, body = null) {
  const modeText = isSafeDemoMode ? '[Safe Demo] ' : '';
  showToast(`${modeText}Dispatching ${channel.toUpperCase()} to ${contactName}...`, 'info');

  try {
    const payload = {
      lead_id: leadId,
      channel: channel,
      sim_days: currentSimDays,
      dry_run: isSafeDemoMode
    };
    if (subject) payload.subject = subject;
    if (body) payload.body = body;

    const res = await fetch('/api/send-message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (data.status === 'success') {
      showToast(data.message || `Successfully sent ${channel.toUpperCase()}`, 'success');
      loadDashboardData();
    } else {
      showToast(`Error: ${data.message}`, 'error');
    }
  } catch (err) {
    showToast(`Failed to send: ${err.message}`, 'error');
  }
};

function formatStatusLabel(status) {
  switch (status) {
    case 'AWAITING_REPLY': return 'Waiting for Reply';
    case 'FOLLOW_UP_DUE': return 'Follow-Up Due';
    case 'SEND_FOLLOW_UP': return 'Follow-Up Due';
    case 'SEND_INITIAL': return 'Ready to Send';
    case 'NOT_CONTACTED': return 'Ready to Send';
    case 'REPLIED': return 'Lead Replied';
    case 'STOPPED_REPLIED': return 'Lead Replied';
    case 'OPTED_OUT': return 'Opted Out';
    case 'MOVE_TO_NURTURE': return 'In Nurture';
    default: return status;
  }
}

function renderActivityFeed(recentMessages) {
  if (!recentMessages || recentMessages.length === 0) {
    elActivityFeed.innerHTML = '<div style="color: var(--color-ink-muted); font-size: 0.82rem;">No activity recorded yet. Click "Send Initial" on any lead to start outreach.</div>';
    elActivityCount.textContent = '0 Events';
    return;
  }

  elActivityCount.textContent = `${recentMessages.length} Events`;
  const html = recentMessages.slice(0, 10).map(m => {
    const sentTime = m.sent_at ? m.sent_at.split('T')[1].substring(0, 5) : (m.created_at ? m.created_at.split('T')[1].substring(0, 5) : '');
    const dateStr = (m.sent_at || m.created_at || '').split('T')[0];

    return `
      <div class="activity-item">
        <div class="activity-left">
          <span class="activity-ch-badge">${m.channel}</span>
          <div>
            <strong>${m.channel.toUpperCase()} to ${escapeHtml(m.lead_id)}</strong>
            <span style="color: var(--color-ink-muted); margin-left: 6px;">${m.subject ? `"${escapeHtml(m.subject.substring(0, 30))}..."` : 'Initial Outreach'}</span>
          </div>
        </div>
        <span class="activity-time">${dateStr} ${sentTime}</span>
      </div>
    `;
  }).join('');

  elActivityFeed.innerHTML = html;
}

// --- MODAL HANDLERS (Feature 1: Inline Draft Editor) ---

let currentModalLead = null;

window.toggleModalHookExpanded = function() {
  const textEl = document.getElementById('modalHookText');
  const btnEl = document.getElementById('btnToggleModalHook');
  if (!textEl || !btnEl) return;
  const isClamped = textEl.classList.contains('modal-hook-clamped');
  if (isClamped) {
    textEl.classList.remove('modal-hook-clamped');
    btnEl.textContent = 'Read less';
  } else {
    textEl.classList.add('modal-hook-clamped');
    btnEl.textContent = 'Read more';
  }
};

window.saveCurrentLeadCrm = async function() {
  if (!currentModalLead) return;
  const leadId = currentModalLead.lead_id;
  const city = (document.getElementById('modalLeadCity')?.value || '').trim();
  const industry = (document.getElementById('modalLeadIndustry')?.value || '').trim();
  const rawOppValue = (document.getElementById('modalLeadOppValue')?.value || '').trim();
  const salesperson = (document.getElementById('modalLeadSalesperson')?.value || '').trim();
  const notes = (document.getElementById('modalLeadNotes')?.value || '').trim();
  const statusEl = document.getElementById('crmSaveStatus');
  const btnSave = document.getElementById('btnSaveCrmDetails');

  let oppValue = null;
  if (rawOppValue !== '') {
    const parsed = Number(rawOppValue);
    if (isNaN(parsed) || parsed < 0) {
      if (statusEl) {
        statusEl.className = 'crm-save-status error';
        statusEl.textContent = 'Invalid amount';
      }
      showToast('Opportunity value must be a valid positive number', 'error');
      return;
    }
    oppValue = parsed;
  }

  if (btnSave) btnSave.disabled = true;
  if (statusEl) {
    statusEl.className = 'crm-save-status';
    statusEl.textContent = 'Saving…';
  }

  try {
    const res = await fetch('/api/update-lead', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        lead_id: leadId,
        city: city || null,
        industry: industry || null,
        opportunity_value: oppValue,
        salesperson: salesperson || null,
        notes: notes || null
      })
    });
    const data = await res.json();
    if (!res.ok || data.status !== 'success') {
      throw new Error(data.message || 'Failed to update CRM details');
    }

    // Update in-memory models
    currentModalLead.city = city || null;
    currentModalLead.industry = industry || null;
    currentModalLead.opportunity_value = oppValue;
    currentModalLead.salesperson = salesperson || null;
    currentModalLead.notes = notes || null;

    if (currentDashboardData && currentDashboardData.leads) {
      const match = currentDashboardData.leads.find(l => l.lead_id === leadId);
      if (match) {
        match.city = city || null;
        match.industry = industry || null;
        match.opportunity_value = oppValue;
        match.salesperson = salesperson || null;
        match.notes = notes || null;
        renderLeadsTable(currentDashboardData.leads);
      }
    }

    if (statusEl) {
      statusEl.className = 'crm-save-status success';
      statusEl.textContent = 'Saved ✓';
      setTimeout(() => { if (statusEl) statusEl.textContent = ''; }, 3000);
    }
    showToast(`CRM details saved for ${currentModalLead.company}`, 'success');
  } catch (err) {
    console.error('Error saving CRM details:', err);
    if (statusEl) {
      statusEl.className = 'crm-save-status error';
      statusEl.textContent = 'Save failed';
    }
    showToast(err.message || 'Error saving CRM details', 'error');
  } finally {
    if (btnSave) btnSave.disabled = false;
  }
};

window.openLeadModal = async function(leadId, initialTab = 'email') {
  const hookEl = elModalHook || document.getElementById('modalHook');
  const historyEl = elModalHistoryList || document.getElementById('modalHistoryList');

  // Show modal immediately with loading state
  if (elModalCompany) elModalCompany.textContent = 'Loading…';
  if (elModalContact) elModalContact.textContent = '';
  if (elModalEmailSubject) elModalEmailSubject.value = '';
  if (elModalEmailBody) elModalEmailBody.value = 'Loading draft…';
  if (elModalSmsBody) elModalSmsBody.value = 'Loading draft…';
  if (elModalWhatsappBody) elModalWhatsappBody.value = 'Loading draft…';
  const preCity = document.getElementById('modalLeadCity');
  const preIndustry = document.getElementById('modalLeadIndustry');
  const preOpp = document.getElementById('modalLeadOppValue');
  const preSales = document.getElementById('modalLeadSalesperson');
  const preNotes = document.getElementById('modalLeadNotes');
  const preStatus = document.getElementById('crmSaveStatus');
  if (preCity) preCity.value = '';
  if (preIndustry) preIndustry.value = '';
  if (preOpp) preOpp.value = '';
  if (preSales) preSales.value = '';
  if (preNotes) preNotes.value = '';
  if (preStatus) { preStatus.textContent = ''; preStatus.className = 'crm-save-status'; }
  if (historyEl) historyEl.innerHTML = '<div class="loading-row"><span class="spinner-inline"></span> Loading history…</div>';
  if (elLeadModal) elLeadModal.style.display = 'flex';

  try {
    const res = await fetch(`/api/lead-details?lead_id=${encodeURIComponent(leadId)}`);
    if (!res.ok) throw new Error('Lead not found');
    const data = await res.json();
    const lead = data.lead;
    currentModalLead = lead;

    // Populate CRM Profile Fields
    const inputCity = document.getElementById('modalLeadCity');
    const inputIndustry = document.getElementById('modalLeadIndustry');
    const inputOppValue = document.getElementById('modalLeadOppValue');
    const inputSalesperson = document.getElementById('modalLeadSalesperson');
    const inputNotes = document.getElementById('modalLeadNotes');
    const statusCrm = document.getElementById('crmSaveStatus');

    if (inputCity) inputCity.value = lead.city || '';
    if (inputIndustry) inputIndustry.value = lead.industry || '';
    if (inputOppValue) inputOppValue.value = (lead.opportunity_value !== null && lead.opportunity_value !== undefined) ? lead.opportunity_value : '';
    if (inputSalesperson) inputSalesperson.value = lead.salesperson || '';
    if (inputNotes) inputNotes.value = lead.notes || '';
    if (statusCrm) { statusCrm.textContent = ''; statusCrm.className = 'crm-save-status'; }

    if (elModalCompany) elModalCompany.textContent = lead.company;
    if (elModalContact) elModalContact.textContent = `${lead.contact_name} (${lead.designation || 'Decision Maker'}) • ${lead.email || lead.phone || ''}`;
    if (hookEl) {
      const hookText = lead.personalization_hook ? String(lead.personalization_hook).trim() : '';
      if (!hookText) {
        hookEl.innerHTML = '';
        hookEl.style.display = 'none';
      } else {
        hookEl.style.display = 'block';
        const isLong = hookText.length > 160;
        hookEl.innerHTML = `
          <div class="modal-hook-wrapper">
            <div class="modal-hook-text ${isLong ? 'modal-hook-clamped' : ''}" id="modalHookText">
              <strong>Personalization Hook:</strong> "${escapeHtml(hookText)}"
            </div>
            ${isLong ? `<button type="button" class="modal-hook-toggle" id="btnToggleModalHook" onclick="toggleModalHookExpanded()">Read more</button>` : ''}
          </div>
        `;
      }
    }

    // Activate selected or default tab
    const activeTab = ['email', 'sms', 'whatsapp', 'timeline', 'history'].includes(initialTab) ? initialTab : 'email';
    elTabBtns.forEach(t => {
      if (t.getAttribute('data-tab') === activeTab) t.classList.add('active');
      else t.classList.remove('active');
    });
    const paneEmail = document.getElementById('tabEmail');
    const paneSms = document.getElementById('tabSms');
    const paneWa = document.getElementById('tabWhatsapp');
    const paneTime = document.getElementById('tabTimeline');
    const paneHist = document.getElementById('tabHistory');
    if (paneEmail) paneEmail.style.display = activeTab === 'email' ? 'block' : 'none';
    if (paneSms) paneSms.style.display = activeTab === 'sms' ? 'block' : 'none';
    if (paneWa) paneWa.style.display = activeTab === 'whatsapp' ? 'block' : 'none';
    if (paneTime) paneTime.style.display = activeTab === 'timeline' ? 'block' : 'none';
    if (paneHist) paneHist.style.display = activeTab === 'history' ? 'block' : 'none';

    const btnEmail = document.getElementById('btnModalSendEmail');
    const btnSms = document.getElementById('btnModalSendSms');
    const btnWa = document.getElementById('btnModalSendWhatsapp');
    if (btnEmail) btnEmail.style.display = activeTab === 'email' ? 'inline-block' : 'none';
    if (btnSms) btnSms.style.display = activeTab === 'sms' ? 'inline-block' : 'none';
    if (btnWa) btnWa.style.display = activeTab === 'whatsapp' ? 'inline-block' : 'none';

    const emailDraft = data.drafts.find(d => d.channel === 'email');
    const smsDraft = data.drafts.find(d => d.channel === 'sms');
    const waDraft = data.drafts.find(d => d.channel === 'whatsapp');

    // Editable draft fields
    if (elModalEmailSubject) elModalEmailSubject.value = emailDraft ? emailDraft.subject : '';
    if (elModalEmailBody) elModalEmailBody.value = emailDraft ? emailDraft.body : '';
    if (elModalSmsBody) elModalSmsBody.value = smsDraft ? smsDraft.body : '';
    if (elModalWhatsappBody) elModalWhatsappBody.value = waDraft ? waDraft.body : '';

    // Conversation Timeline
    const timelineData = data.conversation_timeline || data.timeline || [];
    renderConversationTimeline(timelineData, lead);

    // Sent history
    if (historyEl) {
      if (data.history && data.history.length > 0) {
        historyEl.innerHTML = data.history.map(h => `
          <div class="history-item">
            <div class="history-item-header">
              <span>${h.channel.toUpperCase()} (${h.approved ? 'Approved by ' + (h.approved_by || 'Human') : 'Draft'})</span>
              <span class="mono-data">${h.sent_at || h.created_at}</span>
            </div>
            <div class="history-item-body">${escapeHtml(h.body)}</div>
          </div>
        `).join('');
      } else {
        historyEl.innerHTML = '<div style="color: var(--color-ink-muted); font-size: 0.82rem;">No sent history yet for this lead.</div>';
      }
    }

    // Modal Send Button wiring with live edited content
    const btnSend = document.getElementById('btnModalSendEmail');
    if (btnSend) {
      btnSend.onclick = async () => {
        const subj = elModalEmailSubject.value;
        const body = elModalEmailBody.value;
        closeLeadModal();
        triggerDashboardSend(lead.lead_id, 'email', lead.contact_name, 'SEND_INITIAL', subj, body);
      };
    }

    const btnSendSms = document.getElementById('btnModalSendSms');
    if (btnSendSms) {
      btnSendSms.onclick = async () => {
        const body = elModalSmsBody.value;
        closeLeadModal();
        triggerDashboardSend(lead.lead_id, 'sms', lead.contact_name, 'SEND_INITIAL', null, body);
      };
    }

    const btnSendWhatsapp = document.getElementById('btnModalSendWhatsapp');
    if (btnSendWhatsapp) {
      btnSendWhatsapp.onclick = async () => {
        const body = elModalWhatsappBody.value;
        closeLeadModal();
        triggerDashboardSend(lead.lead_id, 'whatsapp', lead.contact_name, 'SEND_INITIAL', null, body);
      };
    }

  } catch (err) {
    closeLeadModal();
    showToast('Failed to load lead details: ' + err.message, 'error');
  }
};

function renderConversationTimeline(timeline, lead) {
  const timelineEl = document.getElementById('modalTimelineList');
  if (!timelineEl) return;

  if (!timeline || timeline.length === 0) {
    timelineEl.innerHTML = `
      <div class="timeline-empty-state">
        <svg class="timeline-empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
        </svg>
        <div class="timeline-empty-title">No messages yet</div>
        <div class="timeline-empty-desc">Outbound sent messages and inbound lead replies across Email, SMS, and WhatsApp will appear here in chronological order.</div>
      </div>
    `;
    return;
  }

  const channelIcons = {
    email: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>`,
    sms: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>`,
    whatsapp: `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>`
  };

  const getClassificationTag = (cls) => {
    if (!cls) return '';
    const norm = String(cls).toUpperCase().trim();
    let tagClass = 'class-tag-generic';
    let icon = '💬';
    if (norm.includes('MEETING')) {
      tagClass = 'class-tag-meeting';
      icon = '📅';
    } else if (norm.includes('PRICING')) {
      tagClass = 'class-tag-pricing';
      icon = '💰';
    } else if (norm.includes('TECHNICAL') || norm.includes('QUESTION')) {
      tagClass = 'class-tag-technical';
      icon = '⚙️';
    } else if (norm.includes('OPT_OUT') || norm.includes('NOT_INTERESTED') || norm.includes('UNSUBSCRIBE')) {
      tagClass = 'class-tag-notinterested';
      icon = '🛑';
    }
    return `
      <div class="timeline-classification-bar">
        <span class="timeline-class-tag ${tagClass}">
          <span>${icon}</span>
          <span>${escapeHtml(norm)}</span>
        </span>
      </div>
    `;
  };

  timelineEl.innerHTML = timeline.map(item => {
    const isSent = item.type === 'sent';
    const ch = (item.channel || 'email').toLowerCase();
    const chTagClass = `channel-tag-${ch}`;
    const chIcon = channelIcons[ch] || channelIcons.email;
    const senderName = isSent ? 'Sent Outreach' : `${escapeHtml(lead ? lead.contact_name : 'Lead')} (Reply)`;
    const rawContent = item.content || '';
    const isFallback = rawContent.includes('[reply text not available');
    const displayBody = isFallback ? `<span class="timeline-fallback-body">${escapeHtml(rawContent)}</span>` : escapeHtml(rawContent);
    const subjectHtml = (isSent && item.subject) ? `<div class="timeline-subject">Subject: ${escapeHtml(item.subject)}</div>` : '';
    const classHtml = (!isSent && item.classification) ? getClassificationTag(item.classification) : '';

    return `
      <div class="timeline-bubble-wrap ${isSent ? 'sent' : 'received'}">
        <div class="timeline-bubble ${isSent ? 'timeline-bubble-sent' : 'timeline-bubble-received'}">
          <div class="timeline-bubble-header">
            <div class="timeline-meta-left">
              <span class="timeline-sender-label ${isSent ? 'timeline-sender-sent' : 'timeline-sender-received'}">
                ${isSent ? `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>` : `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>`}
                ${senderName}
              </span>
              <span class="timeline-channel-tag ${chTagClass}">
                ${chIcon} ${ch.toUpperCase()}
              </span>
            </div>
            <span class="timeline-timestamp">${escapeHtml(item.timestamp || '—')}</span>
          </div>
          ${subjectHtml}
          <div class="timeline-body">${displayBody}</div>
          ${classHtml}
        </div>
      </div>
    `;
  }).join('');
}

function closeLeadModal() {
  elLeadModal.style.display = 'none';
}

// --- HETVI LEADS PAGE ---

async function loadHetviLeads() {
  if (!elHetviTableBody) return;

  // Show loading state
  elHetviTableBody.innerHTML = '<tr><td colspan="7" class="loading-row"><span class="spinner-inline"></span> Loading leads from Hetvi\'s discovery service...</td></tr>';
  if (elHetviStateMsg) elHetviStateMsg.style.display = 'none';

  try {
    const res = await fetch('/api/fetch-hetvi-leads');
    const data = await res.json();

    if (data.status === 'error') {
      showHetviState('error', `Could not reach Hetvi's lead service — check the network connection. (${data.message || 'Unknown error'})`);
      elHetviTableBody.innerHTML = '<tr><td colspan="7" class="text-center py-4" style="color: var(--text-muted);">Failed to load leads. Click Refresh to retry.</td></tr>';
      updateHetviCounts();
      return;
    }

    hetviLeadsData = (data.leads || []).sort((a, b) => getContactPriority(b) - getContactPriority(a));
    hetviLoaded = true;

    if (hetviLeadsData.length === 0) {
      showHetviState('info', data.message || 'No new leads from Hetvi right now — all available leads have already been activated, or the service has no new results.');
      elHetviTableBody.innerHTML = '<tr><td colspan="7" class="text-center py-4" style="color: var(--text-muted);">No new leads available. All leads have been activated or none are available from Hetvi\'s service.</td></tr>';
      updateHetviCounts();
      return;
    }

    renderHetviTable();
    if (data.filtered_duplicates > 0) {
      showToast(`Loaded ${hetviLeadsData.length} new lead(s) from Hetvi (${data.filtered_duplicates} already activated, filtered out).`, 'info');
    } else {
      showToast(`Loaded ${hetviLeadsData.length} new lead(s) from Hetvi's discovery service.`, 'success');
    }
  } catch (err) {
    console.error('[HetviLeads] Fetch error:', err);
    showHetviState('error', `Could not reach Hetvi's lead service — check the network connection. (${err.message})`);
    elHetviTableBody.innerHTML = '<tr><td colspan="7" class="text-center py-4" style="color: var(--text-muted);">Failed to load leads. Click Refresh to retry.</td></tr>';
    updateHetviCounts();
  }
}

function updateHetviCounts() {
  const total = hetviLeadsData.length;
  let countBoth = 0;
  let countEmailOnly = 0;
  let countPhoneOnly = 0;

  hetviLeadsData.forEach(lead => {
    const hasEmail = Boolean(lead.email && String(lead.email).trim());
    const hasPhone = Boolean(lead.phone && String(lead.phone).trim());
    if (hasEmail && hasPhone) countBoth++;
    else if (hasEmail) countEmailOnly++;
    else if (hasPhone) countPhoneOnly++;
  });

  if (elCountHetviAll) elCountHetviAll.textContent = total;
  if (elCountHetviBoth) elCountHetviBoth.textContent = countBoth;
  if (elCountHetviEmail) elCountHetviEmail.textContent = countEmailOnly;
  if (elCountHetviPhone) elCountHetviPhone.textContent = countPhoneOnly;
}

function showHetviState(type, message) {
  if (!elHetviStateMsg) return;
  elHetviStateMsg.style.display = 'block';
  elHetviStateMsg.className = `hetvi-state-msg hetvi-state-${type}`;
  elHetviStateMsg.textContent = message;
}

function renderHetviTable() {
  if (!elHetviTableBody) return;
  updateHetviCounts();

  if (hetviLeadsData.length === 0) {
    elHetviTableBody.innerHTML = '<tr><td colspan="7" class="text-center py-4" style="color: var(--text-muted);">No new leads from Hetvi right now. Click Refresh to check again.</td></tr>';
    return;
  }

  const query = elHetviSearchInput ? elHetviSearchInput.value.toLowerCase().trim() : '';

  let filtered = hetviLeadsData.filter(lead => {
    // Search query filter
    if (query) {
      const matchCompany = (lead.company || '').toLowerCase().includes(query);
      const matchContact = (lead.contact_name || '').toLowerCase().includes(query);
      const matchHook = (lead.personalization_hook || '').toLowerCase().includes(query);
      if (!matchCompany && !matchContact && !matchHook) return false;
    }

    // Contactability pill filter
    const hasEmail = Boolean(lead.email && String(lead.email).trim());
    const hasPhone = Boolean(lead.phone && String(lead.phone).trim());

    if (hetviActiveFilter === 'both') return (hasEmail && hasPhone);
    if (hetviActiveFilter === 'email') return (hasEmail && !hasPhone);
    if (hetviActiveFilter === 'phone') return (!hasEmail && hasPhone);
    return true; // 'all'
  });

  if (filtered.length === 0) {
    elHetviTableBody.innerHTML = `
      <tr>
        <td colspan="7" style="text-align: center; padding: 2rem; color: var(--color-ink-muted);">
          No Hetvi leads match your current search or filter criteria.
        </td>
      </tr>
    `;
    return;
  }

  const serviceOptionsHtml = SERVICE_OPTIONS.map(s =>
    `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`
  ).join('');

  const rowsHtml = filtered.map(lead => {
    const leadId = lead.lead_id;
    const hookPreview = (lead.personalization_hook || '').length > 150
      ? lead.personalization_hook.substring(0, 150) + '…'
      : (lead.personalization_hook || '—');
    const hasFullText = (lead.personalization_hook || '').length > 150;

    // Email cell: show value + Send Email button, or Not Found badge
    const emailCell = lead.email
      ? `<div class="hetvi-contact-cell">
           <span class="mono-data" style="font-size: 0.78rem;">${escapeHtml(lead.email)}</span>
           <div class="hetvi-channel-actions">
             <button class="ch-action-btn ch-action-email" onclick="openHetviChannelModal('${escapeHtml(leadId)}', 'email')" title="Preview and send Email">
               ✉️ Send Email
             </button>
           </div>
         </div>`
      : `<span class="badge-not-found">Not Found</span>`;

    // Phone cell: show value + warning (if any) + Send SMS & Send WhatsApp buttons
    let phoneCell = '';
    if (lead.phone) {
      const warningBadge = lead.phone_unreachable
        ? `<span class="badge-unreachable" title="${escapeHtml(lead.phone_unreachable_reason || 'May be unreachable for SMS/WhatsApp')}">⚠ ${escapeHtml(lead.phone_unreachable_reason || 'May be unreachable')}</span>`
        : '';
      phoneCell = `
        <div class="hetvi-contact-cell">
          <div class="phone-cell-wrapper">
            <span class="mono-data" style="font-size: 0.78rem;">${escapeHtml(lead.phone)}</span>
            ${warningBadge ? warningBadge : ''}
          </div>
          <div class="hetvi-channel-actions">
            <button class="ch-action-btn ch-action-sms" onclick="openHetviChannelModal('${escapeHtml(leadId)}', 'sms')" title="Preview and send SMS">
              📱 Send SMS
            </button>
            <button class="ch-action-btn ch-action-wa" onclick="openHetviChannelModal('${escapeHtml(leadId)}', 'whatsapp')" title="Preview and send WhatsApp">
              💬 Send WhatsApp
            </button>
          </div>
        </div>
      `;
    } else {
      phoneCell = `<span class="badge-not-found">Not Found</span>`;
    }

    return `
      <tr id="hetvi-row-${escapeHtml(leadId)}" data-lead-id="${escapeHtml(leadId)}">
        <td>
          <div class="company-name">${escapeHtml(lead.company)}</div>
          <div class="contact-name" style="font-size: 0.82rem; margin-top: 2px;">${escapeHtml(lead.contact_name)}</div>
        </td>
        <td>
          <div class="hetvi-hook-preview" id="hetvi-hook-${escapeHtml(leadId)}">
            <span class="hetvi-hook-text">${escapeHtml(hookPreview)}</span>
            ${hasFullText ? `<button class="hetvi-expand-btn" onclick="toggleHetviHook('${escapeHtml(leadId)}')" title="Show full research summary">Show more</button>` : ''}
          </div>
        </td>
        <td>${emailCell}</td>
        <td>${phoneCell}</td>
        <td>
          <select class="form-select hetvi-inline-select" id="hetvi-service-${escapeHtml(leadId)}">
            <option value="">— Select Service —</option>
            ${serviceOptionsHtml}
          </select>
        </td>
        <td>
          <input type="number" class="form-input hetvi-inline-input" id="hetvi-score-${escapeHtml(leadId)}"
                 min="0" max="100" placeholder="0–100">
        </td>
        <td style="text-align: right;">
          <div style="display: flex; gap: 0.4rem; justify-content: flex-end; align-items: center;">
            <button class="btn btn-secondary btn-sm btn-review-draft" onclick="previewHetviLead('${escapeHtml(leadId)}')" title="Preview and review lead details">
              <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M11 2a2 2 0 0 1 2.83 2.83L4.5 14.17 1 15l.83-3.5L11 2z"></path></svg>
              <span>Review & Edit</span>
            </button>
            <button class="btn btn-primary btn-sm hetvi-activate-btn" id="hetvi-activate-${escapeHtml(leadId)}"
                    onclick="activateHetviLead('${escapeHtml(leadId)}')"
                    title="Activate lead into outreach pipeline">
              Activate
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');

  elHetviTableBody.innerHTML = rowsHtml;
}

window.openHetviChannelModal = function(leadId, channel) {
  openLeadModal(leadId, channel);
};

window.previewHetviLead = function(leadId) {
  openLeadModal(leadId, 'email');
};

window.toggleHetviHook = function(leadId) {
  const lead = hetviLeadsData.find(l => l.lead_id === leadId);
  if (!lead) return;
  const container = document.getElementById(`hetvi-hook-${leadId}`);
  if (!container) return;

  const textEl = container.querySelector('.hetvi-hook-text');
  const btnEl = container.querySelector('.hetvi-expand-btn');
  if (!textEl || !btnEl) return;

  const isExpanded = container.classList.contains('is-expanded');
  if (isExpanded) {
    const preview = (lead.personalization_hook || '').substring(0, 150) + '…';
    textEl.textContent = preview;
    btnEl.textContent = 'Show more';
    container.classList.remove('is-expanded');
  } else {
    textEl.textContent = lead.personalization_hook || '';
    btnEl.textContent = 'Show less';
    container.classList.add('is-expanded');
  }
};

window.activateHetviLead = async function(leadId) {
  const lead = hetviLeadsData.find(l => l.lead_id === leadId);
  if (!lead) return;

  const serviceEl = document.getElementById(`hetvi-service-${leadId}`);
  const scoreEl = document.getElementById(`hetvi-score-${leadId}`);

  const service = serviceEl ? serviceEl.value.trim() : '';
  const scoreRaw = scoreEl ? scoreEl.value.trim() : '';
  const scoreVal = scoreRaw !== '' ? parseInt(scoreRaw, 10) : null;

  // Validate score bounds only if entered
  if (scoreVal !== null && (isNaN(scoreVal) || scoreVal < 0 || scoreVal > 100)) {
    showToast('Score must be a number between 0 and 100.', 'error');
    return;
  }

  // lead_status logic per spec:
  // - If BOTH Service and Score were filled in -> QUALIFIED
  // - If EITHER is missing -> NEW
  const hasService = Boolean(service);
  const hasScore = (scoreVal !== null && !isNaN(scoreVal));
  const leadStatus = (hasService && hasScore) ? 'QUALIFIED' : 'NEW';

  // Disable button during network call
  const btnEl = document.getElementById(`hetvi-activate-${leadId}`);
  if (btnEl) {
    btnEl.disabled = true;
    btnEl.textContent = 'Activating…';
  }

  showToast(`Activating ${lead.company} (${leadStatus})...`, 'info');

  try {
    const payload = {
      lead_id: lead.lead_id,
      company: lead.company,
      contact_name: lead.contact_name,
      email: lead.email || '',
      phone: lead.phone || '',
      website: lead.website || '',
      personalization_hook: lead.personalization_hook || '',
      primary_service: service,
      lead_score: hasScore ? String(scoreVal) : '',
      lead_status: leadStatus
    };

    const res = await fetch('/api/add-lead', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (data.status === 'success') {
      showToast(`${lead.company} activated as ${leadStatus}! Visible in Demo.`, 'success');

      // Remove this lead from local array and re-render
      const leadIndex = hetviLeadsData.findIndex(l => l.lead_id === leadId);
      if (leadIndex !== -1) {
        hetviLeadsData.splice(leadIndex, 1);
      }

      renderHetviTable();

      // Refresh dashboard data so the new lead shows up immediately in the Dashboard tab
      loadDashboardData();
    } else {
      showToast(`Error: ${data.message}`, 'error');
      if (btnEl) {
        btnEl.disabled = false;
        btnEl.textContent = 'Activate';
      }
    }
  } catch (err) {
    showToast(`Failed to activate lead: ${err.message}`, 'error');
    if (btnEl) {
      btnEl.disabled = false;
      btnEl.textContent = 'Activate';
    }
  }
};

// --- UTILITIES ---

function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str).replace(/[&<>"']/g, function(m) {
    return {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;'
    }[m];
  });
}

function getContactPriority(lead) {
  if (!lead) return 0;
  const hasEmail = Boolean(lead.email && String(lead.email).trim());
  const hasPhone = Boolean(lead.phone && String(lead.phone).trim());
  if (hasEmail && hasPhone) return 2; // Both available -> Top
  if (hasEmail || hasPhone) return 1; // One available -> Middle
  return 0; // Neither available -> Bottom
}

// ==============================================================================
// FEATURE 1: VOICE COMMAND ASSISTANT (SAFE-ACTIONS-ONLY)
// ==============================================================================

let isRecordingVoice = false;
let voiceMediaRecorder = null;
let voiceAudioChunks = [];
let voiceStream = null;

function setupVoiceAssistant() {
  const btnVoice = document.getElementById('btnVoiceAssistant');
  const labelVoice = document.getElementById('voiceAssistantLabel');
  if (!btnVoice) return;

  btnVoice.addEventListener('click', async () => {
    if (isRecordingVoice) {
      stopVoiceRecording();
    } else {
      startVoiceRecording();
    }
  });

  async function startVoiceRecording() {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        startWebSpeechFallback();
        return;
      }

      voiceStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      voiceAudioChunks = [];
      voiceMediaRecorder = new MediaRecorder(voiceStream, { mimeType: 'audio/webm' });

      voiceMediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          voiceAudioChunks.push(e.data);
        }
      };

      voiceMediaRecorder.onstop = async () => {
        const audioBlob = new Blob(voiceAudioChunks, { type: 'audio/webm' });
        if (voiceStream) {
          voiceStream.getTracks().forEach(t => t.stop());
          voiceStream = null;
        }
        await sendVoiceAudioToBackend(audioBlob);
      };

      voiceMediaRecorder.start();
      isRecordingVoice = true;
      btnVoice.classList.add('is-recording');
      if (labelVoice) labelVoice.textContent = 'Listening…';
      showToast('Listening for voice command… (Speak now, click button again to finish)', 'info');

    } catch (err) {
      console.warn('Microphone stream error, switching to Web Speech fallback:', err);
      startWebSpeechFallback();
    }
  }

  function stopVoiceRecording() {
    if (voiceMediaRecorder && voiceMediaRecorder.state !== 'inactive') {
      voiceMediaRecorder.stop();
    }
    isRecordingVoice = false;
    btnVoice.classList.remove('is-recording');
    if (labelVoice) labelVoice.textContent = 'Processing…';
  }

  function startWebSpeechFallback() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      const manualCmd = prompt("Voice Assistant — Speak or enter your dashboard command:\n(e.g. 'switch to hetvi', 'search BrightCart', 'open BrightCart email')");
      if (manualCmd) {
        sendVoiceTextToBackend(manualCmd);
      }
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    btnVoice.classList.add('is-recording');
    if (labelVoice) labelVoice.textContent = 'Listening…';
    showToast('Listening via browser speech recognition…', 'info');

    recognition.onresult = (event) => {
      const speechResult = event.results[0][0].transcript;
      btnVoice.classList.remove('is-recording');
      if (labelVoice) labelVoice.textContent = 'Processing…';
      sendVoiceTextToBackend(speechResult);
    };

    recognition.onerror = (event) => {
      btnVoice.classList.remove('is-recording');
      if (labelVoice) labelVoice.textContent = 'Voice';
      showToast('Speech recognition error: ' + (event.error || 'Unknown error'), 'error');
    };

    recognition.onend = () => {
      btnVoice.classList.remove('is-recording');
      if (labelVoice) labelVoice.textContent = 'Voice';
    };

    recognition.start();
  }

  async function sendVoiceAudioToBackend(blob) {
    if (labelVoice) labelVoice.textContent = 'Processing…';
    try {
      const reader = new FileReader();
      reader.readAsDataURL(blob);
      reader.onloadend = async () => {
        const base64Audio = reader.result.split(',')[1];
        try {
          const res = await fetch('/api/voice-command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ audio_base64: base64Audio, format: 'webm' })
          });
          const data = await res.json();
          handleVoiceResponse(data);
        } catch (e) {
          showToast('Voice command request failed: ' + e.message, 'error');
        } finally {
          if (labelVoice) labelVoice.textContent = 'Voice';
        }
      };
    } catch (err) {
      if (labelVoice) labelVoice.textContent = 'Voice';
      showToast('Audio processing failed: ' + err.message, 'error');
    }
  }

  async function sendVoiceTextToBackend(text) {
    if (!text || !text.trim()) {
      if (labelVoice) labelVoice.textContent = 'Voice';
      return;
    }
    try {
      const res = await fetch('/api/voice-command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text })
      });
      const data = await res.json();
      handleVoiceResponse(data);
    } catch (e) {
      showToast('Voice command failed: ' + e.message, 'error');
    } finally {
      if (labelVoice) labelVoice.textContent = 'Voice';
    }
  }

  function handleVoiceResponse(data) {
    if (!data) return;

    if (data.status === 'rejected' || (data.permitted === false && data.action !== 'unrecognized')) {
      showToast(data.message || 'Action not permitted via voice', 'error');
      return;
    }

    if (data.status === 'unrecognized' || data.action === 'unrecognized') {
      showToast(data.message || 'Voice command not recognized', 'warning');
      return;
    }

    if (data.status === 'success' && data.permitted) {
      showToast(data.message || `Voice: ${data.action}`, 'info');
      executeVoiceAction(data.action, data.params || {});
    } else {
      showToast(data.message || 'Voice processing error', 'error');
    }
  }
}

function executeVoiceAction(action, params) {
  switch (action) {
    case 'switch_tab': {
      const tab = (params.tab_name || '').toLowerCase();
      if (tab.includes('hetvi') || tab.includes('discovery') || tab.includes('lead') || tab.includes('dash')) {
        switchView('hetvi');
      } else {
        switchView('dashboard');
      }
      break;
    }

    case 'search_leads': {
      const q = params.query || '';
      if (currentView === 'hetvi') {
        if (elHetviSearchInput) {
          elHetviSearchInput.value = q;
          renderHetviTable();
        }
      } else {
        if (elSearchInput) {
          elSearchInput.value = q;
          renderTable();
        }
      }
      break;
    }

    case 'open_lead_modal': {
      const targetCompany = (params.company_name || '').toLowerCase().trim();
      const allLeads = (currentDashboardData && currentDashboardData.leads) ? currentDashboardData.leads : [];
      const match = allLeads.find(l => 
        (l.company && l.company.toLowerCase().includes(targetCompany)) ||
        (l.contact_name && l.contact_name.toLowerCase().includes(targetCompany))
      );
      if (match) {
        if (currentView !== 'dashboard') switchView('dashboard');
        openLeadModal(match.lead_id, 'email');
      } else {
        showToast(`Could not find lead matching "${params.company_name}"`, 'warning');
      }
      break;
    }

    case 'open_channel_preview': {
      const targetCompany = (params.company_name || '').toLowerCase().trim();
      const channel = (params.channel || 'email').toLowerCase().trim();
      const allLeads = (currentDashboardData && currentDashboardData.leads) ? currentDashboardData.leads : [];
      const match = allLeads.find(l => 
        (l.company && l.company.toLowerCase().includes(targetCompany)) ||
        (l.contact_name && l.contact_name.toLowerCase().includes(targetCompany))
      );
      if (match) {
        if (currentView !== 'dashboard') switchView('dashboard');
        const validChannel = ['email', 'sms', 'whatsapp'].includes(channel) ? channel : 'email';
        openLeadModal(match.lead_id, validChannel);
      } else {
        showToast(`Could not find lead matching "${params.company_name}"`, 'warning');
      }
      break;
    }

    case 'add_note': {
      const targetCompany = (params.company_name || '').toLowerCase().trim();
      const noteText = params.note_text || '';
      const allLeads = (currentDashboardData && currentDashboardData.leads) ? currentDashboardData.leads : [];
      const match = allLeads.find(l => 
        (l.company && l.company.toLowerCase().includes(targetCompany)) ||
        (l.contact_name && l.contact_name.toLowerCase().includes(targetCompany))
      );
      if (match) {
        openLeadModal(match.lead_id, 'email').then(() => {
          const notesInput = document.getElementById('modalLeadNotes');
          if (notesInput) {
            notesInput.value = noteText;
            saveCurrentLeadCrm();
          }
        });
      } else {
        showToast(`Note logged for ${params.company_name}: "${noteText}"`, 'success');
      }
      break;
    }

    case 'filter_by_status': {
      const rawStatus = (params.status || 'all').toLowerCase();
      let targetFilter = 'all';
      if (rawStatus.includes('await') || rawStatus.includes('wait')) targetFilter = 'AWAITING_REPLY';
      else if (rawStatus.includes('due') || rawStatus.includes('follow')) targetFilter = 'FOLLOW_UP_DUE';
      else if (rawStatus.includes('repli') || rawStatus.includes('hot')) targetFilter = 'REPLIED';
      else if (rawStatus.includes('opt') || rawStatus.includes('unsub')) targetFilter = 'OPTED_OUT';
      else targetFilter = 'all';

      elFilterPills.forEach(pill => {
        if (pill.getAttribute('data-filter') === targetFilter) {
          elFilterPills.forEach(p => p.classList.remove('active'));
          pill.classList.add('active');
          activeFilter = targetFilter;
          renderTable();
        }
      });
      break;
    }

    default:
      console.warn('Unhandled voice action:', action);
  }
}

