"use strict";

const byId = (id) => document.getElementById(id);
const all = (selector, root = document) => Array.from(root.querySelectorAll(selector));

const state = {
  reports: [],
  activeReport: null,
  latestFilename: null,
  generatedFilename: null,
  diagnosticRunning: false,
  taskStartedAt: 0,
  taskTimerId: null,
  coreBusy: false,
  configuration: null,
  responseMode: "quick",
  models: [],
  modelPollId: null,
  chatHistoryLoaded: false,
  baselineFilename: null,
  lastComparison: null,
  knowledgeSummary: null,
  knowledgeCollections: [],
  knowledgeDocuments: [],
  knowledgeCollectionId: "",
  selectedKnowledgeDocuments: new Set(),
  knowledgeBusy: false,
  monitorData: null,
  monitorPollId: null,
  monitorAlertIds: new Set(),
  monitorAlertsReady: false,
  monitorConfigDirty: false,
  monitorRefreshing: false,
  incidents: [],
  incidentSummary: {},
  activeIncidentId: null,
  incidentsRefreshing: false,
  notificationsEnabled: false,
};

const typeLabels = {
  system: "Sistema",
  network: "Rede",
  full: "Sistema + Rede",
  legacy: "Relatório legado",
};

const severityLabels = {
  normal: "Normal",
  attention: "Atenção",
  critical: "Crítico",
};

const incidentStatusLabels = {
  open: "Em aberto",
  investigating: "Investigando",
  resolved: "Resolvido",
};

const profileLabels = {
  auto: "Automático",
  fast: "Rápido",
  balanced: "Balanceado",
  quality: "Qualidade",
  custom: "Personalizado",
};

function makeElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = String(text);
  return element;
}

function icon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `#icon-${name}`);
  svg.appendChild(use);
  return svg;
}

async function api(path, options = {}) {
  const headers = { Accept: "application/json", ...(options.headers || {}) };
  if (options.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  const response = await fetch(path, { ...options, headers });
  let data;
  try {
    data = await response.json();
  } catch {
    data = {};
  }
  if (!response.ok) {
    throw new Error(data.error || `Falha HTTP ${response.status}`);
  }
  return data;
}

function clamp(value, min = 0, max = 100) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.min(Math.max(number, min), max) : min;
}

function formatBytes(value, decimals = 1) {
  const bytes = Number(value);
  if (!Number.isFinite(bytes) || bytes < 0) return "—";
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / (1024 ** index)).toFixed(index === 0 ? 0 : decimals)} ${units[index]}`;
}

function formatRate(value) {
  const formatted = formatBytes(value);
  return formatted === "—" ? formatted : `${formatted}/s`;
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(date);
}

function formatTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit" }).format(date);
}

function formatDuration(seconds) {
  const total = Number(seconds);
  if (!Number.isFinite(total)) return "—";
  if (total < 1) return `${Math.round(total * 1000)} ms`;
  if (total < 60) return `${total.toFixed(1)} s`;
  const minutes = Math.floor(total / 60);
  const rest = Math.round(total % 60);
  return `${minutes} min ${rest} s`;
}

function diagnosticLabel(type) {
  return typeLabels[type] || String(type || "Diagnóstico");
}

function severityBadge(severity) {
  const safeSeverity = Object.hasOwn(severityLabels, severity) ? severity : "attention";
  return makeElement(
    "span",
    `severity-badge severity-${safeSeverity}`,
    severityLabels[safeSeverity],
  );
}

function updateClock() {
  const date = new Date();
  const clock = byId("clock");
  clock.dateTime = date.toISOString();
  clock.textContent = new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function setStatusPill(element, mode, text) {
  element.classList.remove("is-online", "is-offline", "is-checking");
  element.classList.add(`is-${mode}`);
  const label = element.querySelector("span:last-child");
  if (label) label.textContent = text;
}

function setCoreState(mode, title, description) {
  const visual = byId("coreVisual");
  const container = document.querySelector(".core-state");
  visual.dataset.state = mode;
  container.classList.remove("is-ready", "is-working", "is-warning", "is-error");
  container.classList.add(`is-${mode}`);
  byId("coreStateTitle").textContent = title;
  byId("coreStateText").textContent = description;
}

function showToast(title, message, isError = false) {
  const toast = makeElement("div", `toast${isError ? " is-error" : ""}`);
  const marker = makeElement("span", isError ? "severity-critical" : "severity-normal", isError ? "●" : "●");
  const copy = makeElement("div");
  copy.append(makeElement("strong", "", title), makeElement("p", "", message));
  const close = makeElement("button", "", "×");
  close.type = "button";
  close.setAttribute("aria-label", "Fechar aviso");
  close.addEventListener("click", () => toast.remove());
  toast.append(marker, copy, close);
  byId("toastRegion").appendChild(toast);
  window.setTimeout(() => toast.remove(), 5200);
}

function closeSidebar() {
  document.body.classList.remove("sidebar-open");
  byId("menuToggle").setAttribute("aria-expanded", "false");
}

function navigate(viewName) {
  all("[data-view-panel]").forEach((panel) => {
    const active = panel.dataset.viewPanel === viewName;
    panel.hidden = !active;
    panel.classList.toggle("is-active", active);
  });
  all(".nav-item[data-view]").forEach((button) => {
    const active = button.dataset.view === viewName;
    button.classList.toggle("is-active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  closeSidebar();
  window.scrollTo({ top: 0, behavior: "smooth" });
  if (viewName === "reports") refreshReports();
  if (viewName === "knowledge") refreshKnowledge();
  if (viewName === "monitor") refreshMonitor(false);
  if (viewName === "incidents") refreshIncidents(false);
  if (viewName === "overview") refreshSystem();
  if (viewName === "settings") {
    refreshConfiguration();
    refreshModels(false);
    refreshBenchmark();
  }
  if (viewName === "assistant") refreshChatHistory();
}

function updateHealthUi(data) {
  setStatusPill(byId("llamaStatus"), data.llama_online ? "online" : "offline", data.llama_online ? "IA local online" : "IA local offline");
  setStatusPill(byId("assistantModelStatus"), data.llama_online ? "online" : "offline", data.llama_online ? "Modelo disponível" : "Modelo offline");
  byId("webStatusDot").classList.remove("is-offline");
  byId("webStatusDot").classList.add("is-online");
  byId("appVersion").textContent = `Versão ${data.version}`;
  byId("settingsLlamaUrl").textContent = data.llama_url || "—";
  byId("settingsLlamaState").textContent = data.llama_online ? "Online" : "Offline";
  byId("settingsActiveModel").textContent = data.model || "Não configurado";
  byId("settingsWebUrl").textContent = data.web || "—";
  byId("settingsVersion").textContent = data.version || "—";
  byId("settingsMetricsState").textContent = data.metrics_available ? "Disponível" : "Dependência ausente";
  if (!state.monitorData) {
    const runtime = {
      available: data.monitor_available !== false,
      running: Boolean(data.monitor_running),
    };
    updateMonitorStatus(runtime);
  }
  if (!state.coreBusy) {
    if (data.llama_online) setCoreState("ready", "Sistema pronto", "IA local disponível");
    else setCoreState("warning", "Interface pronta", "Inicie o servidor de IA");
  }
}

function setResponseMode(mode) {
  const safeMode = mode === "deep" ? "deep" : "quick";
  state.responseMode = safeMode;
  all("[data-response-mode]").forEach((button) => {
    const active = button.dataset.responseMode === safeMode;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  const deep = safeMode === "deep";
  byId("responseModeTitle").textContent = deep ? "Análise profunda" : "Modo rápido";
  byId("responseModeDescription").textContent = deep
    ? "Raciocínio ampliado para situações técnicas mais complexas."
    : "Menor espera para perguntas do dia a dia.";
}

function updateConfigurationUi(data, syncResponseMode = true) {
  state.configuration = data;
  const config = data.config || {};
  const hardware = data.hardware || {};
  const runtime = data.runtime || {};
  const recommended = data.recommended_profile || "balanced";

  const profileInput = document.querySelector(`input[name="profile"][value="${config.profile || "auto"}"]`);
  if (profileInput) profileInput.checked = true;
  byId("defaultMode").value = config.default_mode || "quick";
  byId("contextSize").value = String(config.context_size || 4096);
  byId("threads").value = String(config.threads ?? 0);
  byId("gpuLayers").value = String(config.gpu_layers ?? 0);

  byId("settingsCpuName").textContent = hardware.cpu_name || "Processador não identificado";
  byId("settingsCores").textContent = `${hardware.physical_cores || "—"} físicos / ${hardware.logical_cores || "—"} threads`;
  byId("settingsRam").textContent = hardware.memory_total_bytes
    ? `${formatBytes(hardware.memory_total_bytes)} detectados`
    : "—";
  byId("settingsGraphics").textContent = hardware.graphics_name || "—";

  const recommendedLabel = profileLabels[recommended] || recommended;
  byId("recommendedProfileBadge").textContent = `${recommendedLabel} recomendado`;
  byId("profileRecommendation").textContent = data.recommendation_reason || "Perfil calculado conforme o hardware.";

  (data.profiles || []).forEach((profile) => {
    const status = document.querySelector(`[data-profile-status="${profile.id}"]`);
    const card = document.querySelector(`[data-profile-card="${profile.id}"]`);
    if (!status || !card) return;
    status.textContent = profile.installed ? "Instalado" : `Falta baixar • ${profile.approx_size}`;
    status.classList.toggle("is-ready", Boolean(profile.installed));
    status.classList.toggle("is-missing", !profile.installed);
    card.classList.toggle("is-recommended", profile.id === recommended);
  });

  const activeLabel = profileLabels[runtime.active_profile] || runtime.active_profile || "Automático";
  byId("assistantProfileBadge").textContent = `Perfil ${activeLabel}`;
  byId("settingsActiveModel").textContent = runtime.active_model || "Não configurado";
  byId("runtimeSummary").textContent = [
    `Em uso: ${activeLabel}`,
    runtime.active_model || "modelo não instalado",
    `${runtime.threads || "—"} threads`,
    `contexto ${Number(runtime.context_size || 0).toLocaleString("pt-BR")}`,
    `${runtime.gpu_layers || 0} camadas na GPU`,
  ].join(" • ");

  if (syncResponseMode) setResponseMode(config.default_mode || "quick");
}

async function refreshConfiguration() {
  try {
    const data = await api("/api/config");
    updateConfigurationUi(data, state.configuration === null);
    return data;
  } catch (error) {
    byId("runtimeSummary").textContent = "Não foi possível carregar a otimização local.";
    return null;
  }
}

async function saveConfiguration(event) {
  event.preventDefault();
  const submit = byId("saveSettings");
  const selectedProfile = document.querySelector('input[name="profile"]:checked');
  const payload = {
    profile: selectedProfile?.value || "auto",
    default_mode: byId("defaultMode").value,
    context_size: Number(byId("contextSize").value),
    threads: Number(byId("threads").value),
    gpu_layers: Number(byId("gpuLayers").value),
  };
  submit.disabled = true;
  try {
    const data = await api("/api/config", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    updateConfigurationUi(data, true);
    if (data.restart_required) {
      showToast("Configuração salva", "Reinicie o HERMES para aplicar o novo perfil de execução.");
    } else {
      showToast("Configuração salva", "Preferências atualizadas com sucesso.");
    }
  } catch (error) {
    showToast("Falha ao salvar", error.message, true);
  } finally {
    submit.disabled = false;
  }
}

function modelDownloadActive(download = {}) {
  return ["starting", "downloading", "cancelling"].includes(download.status);
}

function updateModelManagerUi(data) {
  state.models = data.profiles || [];
  const download = data.download || { status: "idle" };
  const installedCount = state.models.filter((profile) => profile.installed).length;
  byId("modelManagerState").textContent = `${installedCount} de ${state.models.length} modelos instalados`;

  state.models.forEach((profile) => {
    const status = document.querySelector(`[data-profile-status="${profile.id}"]`);
    if (status) {
      status.textContent = profile.installed
        ? "Instalado"
        : profile.partial_bytes
          ? `Pausado em ${formatBytes(profile.partial_bytes)}`
          : `Falta baixar • ${profile.approx_size}`;
      status.classList.toggle("is-ready", Boolean(profile.installed));
      status.classList.toggle("is-missing", !profile.installed);
    }
    const button = document.querySelector(`[data-download-profile="${profile.id}"]`);
    if (button) {
      button.disabled = Boolean(profile.installed) || modelDownloadActive(download);
      button.textContent = profile.installed
        ? `${profileLabels[profile.id] || profile.id} instalado`
        : profile.partial_bytes
          ? `Continuar ${profileLabels[profile.id] || profile.id}`
          : `Baixar ${profileLabels[profile.id] || profile.id}`;
    }
  });

  const progress = byId("downloadProgress");
  const showProgress = download.status && download.status !== "idle";
  progress.hidden = !showProgress;
  if (showProgress) {
    const profile = state.models.find((item) => item.id === download.profile);
    byId("downloadTitle").textContent = profile?.model || download.filename || "Modelo local";
    const percent = Number(download.percent);
    const knownPercent = Number.isFinite(percent);
    byId("downloadNumbers").textContent = download.total_bytes
      ? `${formatBytes(download.downloaded_bytes)} / ${formatBytes(download.total_bytes)}${knownPercent ? ` • ${percent.toFixed(1)}%` : ""}`
      : formatBytes(download.downloaded_bytes || 0);
    byId("downloadProgressBar").style.width = knownPercent ? `${clamp(percent)}%` : "34%";
    byId("downloadProgressBar").classList.toggle("is-indeterminate", !knownPercent && modelDownloadActive(download));
    byId("downloadMessage").textContent = download.message || "Processando…";
    byId("cancelModelDownload").hidden = !["starting", "downloading", "cancelling"].includes(download.status);
    byId("cancelModelDownload").disabled = download.status === "cancelling";
  }

  if (modelDownloadActive(download)) startModelPolling();
  else stopModelPolling();
  if (download.status === "completed") {
    refreshConfiguration();
    refreshHealth().catch(() => {});
  }
}

async function refreshModels(showError = false) {
  try {
    const data = await api("/api/models");
    updateModelManagerUi(data);
    return data;
  } catch (error) {
    byId("modelManagerState").textContent = "Gerenciador indisponível";
    if (showError) showToast("Modelos indisponíveis", error.message, true);
    return null;
  }
}

function startModelPolling() {
  if (state.modelPollId) return;
  state.modelPollId = window.setInterval(() => refreshModels(false), 1000);
}

function stopModelPolling() {
  if (!state.modelPollId) return;
  window.clearInterval(state.modelPollId);
  state.modelPollId = null;
}

async function requestModelDownload(profileId) {
  const profile = state.models.find((item) => item.id === profileId);
  if (!profile) return;
  const confirmed = window.confirm(
    `Baixar ${profile.model} (${profile.approx_size}) da organização oficial Qwen?\n\nO arquivo ficará somente na pasta local do HERMES.`,
  );
  if (!confirmed) return;
  try {
    const data = await api("/api/models/download", {
      method: "POST",
      body: JSON.stringify({ profile: profileId }),
    });
    updateModelManagerUi({ profiles: state.models, download: data.download });
    showToast("Download iniciado", "Você pode acompanhar ou pausar na área de Configurações.");
  } catch (error) {
    showToast("Download não iniciado", error.message, true);
  }
}

async function pauseModelDownload() {
  try {
    const data = await api("/api/models/cancel", { method: "POST", body: "{}" });
    updateModelManagerUi({ profiles: state.models, download: data.download });
  } catch (error) {
    showToast("Não foi possível pausar", error.message, true);
  }
}

function renderBenchmark(result) {
  if (!result) return;
  byId("benchmarkResult").hidden = false;
  if (Number.isFinite(Number(result.tokens_per_second))) {
    byId("benchmarkValue").textContent = `${Number(result.tokens_per_second).toLocaleString("pt-BR")} tok/s`;
  } else {
    byId("benchmarkValue").textContent = `${Number(result.cpu_throughput_mb_s || 0).toLocaleString("pt-BR")} MB/s CPU`;
  }
  byId("benchmarkGrade").textContent = result.grade_label || "Teste concluído";
  const details = [
    result.model,
    `duração ${formatDuration(result.duration_seconds)}`,
    result.recommended_threads ? `${result.recommended_threads} threads recomendadas` : null,
  ].filter(Boolean);
  byId("benchmarkDetails").textContent = `${details.join(" • ")} — ${result.message || ""}`;
}

async function refreshBenchmark() {
  try {
    const data = await api("/api/benchmark");
    if (data.benchmark) renderBenchmark(data.benchmark);
  } catch {
    // O primeiro teste ainda pode não existir.
  }
}

async function runBenchmark() {
  const button = byId("runBenchmark");
  button.disabled = true;
  button.querySelector("span").textContent = "Testando…";
  state.coreBusy = true;
  setCoreState("working", "Medindo desempenho", "Não feche o HERMES");
  try {
    const data = await api("/api/benchmark", { method: "POST", body: "{}" });
    renderBenchmark(data.benchmark);
    showToast("Teste concluído", data.benchmark.grade_label || "Desempenho local medido.");
    setCoreState("ready", "Teste concluído", data.benchmark.grade_label || "Desempenho medido");
  } catch (error) {
    showToast("Teste não concluído", error.message, true);
    setCoreState("error", "Falha no teste", error.message);
  } finally {
    button.disabled = false;
    button.querySelector("span").textContent = "Testar agora";
    state.coreBusy = false;
  }
}

async function refreshHealth() {
  try {
    const data = await api("/api/health");
    updateHealthUi(data);
    return data;
  } catch (error) {
    setStatusPill(byId("llamaStatus"), "offline", "Servidor indisponível");
    setStatusPill(byId("assistantModelStatus"), "offline", "Servidor indisponível");
    byId("webStatusDot").classList.remove("is-online");
    byId("webStatusDot").classList.add("is-offline");
    if (!state.coreBusy) setCoreState("error", "Interface desconectada", "Verifique o servidor web");
    throw error;
  }
}

function updateRing(ringId, valueId, detailId, percent, detail) {
  const safeValue = clamp(percent);
  byId(ringId).style.setProperty("--value", safeValue.toFixed(1));
  byId(valueId).textContent = Number.isFinite(Number(percent)) ? `${Math.round(Number(percent))}%` : "—";
  byId(detailId).textContent = detail;
}

function clearMetrics(reason = "Métricas indisponíveis") {
  updateRing("cpuRing", "cpuValue", "cpuDetail", Number.NaN, reason);
  updateRing("memoryRing", "memoryValue", "memoryDetail", Number.NaN, reason);
  updateRing("diskRing", "diskValue", "diskDetail", Number.NaN, reason);
  byId("networkUp").textContent = "—";
  byId("networkDown").textContent = "—";
  byId("networkDetail").textContent = reason;
}

function updateSystemUi(data) {
  byId("hostCardTitle").textContent = data.hostname || "Host local";
  byId("hostOs").textContent = [data.system, data.release].filter(Boolean).join(" ") || "Sistema desconhecido";
  const metrics = data.metrics || {};
  if (!metrics.available) {
    clearMetrics("Instale psutil");
    byId("settingsMetricsState").textContent = "Dependência ausente";
    return;
  }

  const cpu = metrics.cpu || {};
  const memory = metrics.memory || {};
  const disk = metrics.disk || {};
  const network = metrics.network || {};
  const cpuDetail = cpu.frequency_mhz
    ? `${Number(cpu.frequency_mhz).toLocaleString("pt-BR")} MHz • ${cpu.physical_cores || "—"} núcleos / ${cpu.logical_cores || "—"} threads`
    : `${cpu.logical_cores || "—"} threads`;
  updateRing("cpuRing", "cpuValue", "cpuDetail", cpu.percent, cpuDetail);
  updateRing(
    "memoryRing",
    "memoryValue",
    "memoryDetail",
    memory.percent,
    `${formatBytes(memory.used_bytes)} / ${formatBytes(memory.total_bytes)}`,
  );
  updateRing(
    "diskRing",
    "diskValue",
    "diskDetail",
    disk.percent,
    `${formatBytes(disk.used_bytes)} / ${formatBytes(disk.total_bytes)}`,
  );
  byId("networkUp").textContent = formatRate(network.sent_bytes_per_second);
  byId("networkDown").textContent = formatRate(network.received_bytes_per_second);
  byId("networkDetail").textContent = "Tráfego do host";
  byId("settingsMetricsState").textContent = "Disponível";
}

async function refreshSystem() {
  try {
    const data = await api("/api/system");
    updateSystemUi(data);
    return data;
  } catch (error) {
    clearMetrics("Servidor indisponível");
    return null;
  }
}

function updateMonitorStatus(runtime = {}) {
  const running = Boolean(runtime.running);
  const available = runtime.available !== false;
  const pill = byId("monitorTopStatus");
  pill.classList.remove("is-online", "is-offline", "is-checking");
  pill.classList.add(running ? "is-online" : available ? "is-checking" : "is-offline");
  const label = pill.querySelector("span:last-child");
  if (label) label.textContent = running ? "Monitor ativo" : available ? "Monitor parado" : "Monitor indisponível";

  const badge = byId("monitorModeBadge");
  badge.classList.remove("is-running", "is-stopped", "is-error");
  badge.classList.add(running ? "is-running" : available ? "is-stopped" : "is-error");
  badge.textContent = running ? "Coleta ativa" : available ? "Parado" : "Indisponível";
}

function monitorLevel(value, warning, critical) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "unknown";
  if (number >= Number(critical)) return "critical";
  if (number >= Number(warning)) return "attention";
  return "normal";
}

function updateMonitorResource(resource, latest, summary, config) {
  const names = { cpu: "Cpu", memory: "Memory", disk: "Disk" };
  const key = names[resource];
  const value = latest?.[`${resource}_percent`];
  const number = Number(value);
  const known = Number.isFinite(number);
  byId(`monitor${key}Value`).textContent = known ? `${number.toFixed(1)}%` : "—";
  byId(`monitor${key}Bar`).style.width = known ? `${clamp(number)}%` : "0%";
  const average = summary?.[`${resource}_average`];
  const peak = summary?.[`${resource}_peak`];
  byId(`monitor${key}Average`).textContent = Number.isFinite(Number(average))
    ? `Média 24 h: ${Number(average).toFixed(1)}%`
    : "Média 24 h: —";
  byId(`monitor${key}Peak`).textContent = Number.isFinite(Number(peak))
    ? `Pico: ${Number(peak).toFixed(1)}%`
    : "Pico: —";
  const card = document.querySelector(`.monitor-resource-card[data-resource="${resource}"]`);
  if (card) {
    card.dataset.level = monitorLevel(
      value,
      config?.[`${resource}_warning`],
      config?.[`${resource}_critical`],
    );
  }
}

function drawMonitorChart(samples = []) {
  const canvas = byId("monitorChart");
  const empty = byId("monitorChartEmpty");
  const context = canvas.getContext("2d");
  const rect = canvas.getBoundingClientRect();
  if (!context || rect.width < 120 || rect.height < 100) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const width = Math.round(rect.width);
  const height = Math.round(rect.height);
  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  context.setTransform(dpr, 0, 0, dpr, 0, 0);
  context.clearRect(0, 0, width, height);
  empty.hidden = samples.length > 0;
  if (!samples.length) return;

  const padding = { top: 22, right: 18, bottom: 34, left: 43 };
  const graphWidth = width - padding.left - padding.right;
  const graphHeight = height - padding.top - padding.bottom;
  context.font = '10px "Segoe UI", sans-serif';
  context.textAlign = "right";
  context.textBaseline = "middle";
  [0, 25, 50, 75, 100].forEach((value) => {
    const y = padding.top + graphHeight - (value / 100) * graphHeight;
    context.strokeStyle = "rgba(131, 162, 199, 0.13)";
    context.lineWidth = 1;
    context.beginPath();
    context.moveTo(padding.left, y);
    context.lineTo(width - padding.right, y);
    context.stroke();
    context.fillStyle = "#8293aa";
    context.fillText(`${value}%`, padding.left - 8, y);
  });

  const series = [
    ["cpu_percent", "#39d1ff"],
    ["memory_percent", "#9b8cff"],
    ["disk_percent", "#2ddb88"],
  ];
  series.forEach(([field, colour]) => {
    context.strokeStyle = colour;
    context.lineWidth = 2;
    context.lineJoin = "round";
    context.lineCap = "round";
    context.beginPath();
    samples.forEach((sample, index) => {
      const x = padding.left + (samples.length === 1 ? graphWidth : (index / (samples.length - 1)) * graphWidth);
      const y = padding.top + graphHeight - (clamp(sample[field]) / 100) * graphHeight;
      if (index === 0) context.moveTo(x, y);
      else context.lineTo(x, y);
    });
    context.stroke();
    const last = samples[samples.length - 1];
    const lastY = padding.top + graphHeight - (clamp(last[field]) / 100) * graphHeight;
    context.fillStyle = colour;
    context.beginPath();
    context.arc(width - padding.right, lastY, 3.5, 0, Math.PI * 2);
    context.fill();
  });

  context.fillStyle = "#8293aa";
  context.textBaseline = "bottom";
  context.textAlign = "left";
  context.fillText(formatTime(samples[0].recorded_at), padding.left, height - 4);
  context.textAlign = "right";
  context.fillText(formatTime(samples[samples.length - 1].recorded_at), width - padding.right, height - 4);
}

function populateMonitorConfig(config = {}) {
  if (state.monitorConfigDirty) return;
  byId("monitorInterval").value = String(config.interval_seconds || 15);
  byId("monitorConsecutive").value = String(config.consecutive_samples || 3);
  byId("monitorRetention").value = String(config.retention_hours || 168);
  ["cpu", "memory", "disk"].forEach((resource) => {
    const key = resource[0].toUpperCase() + resource.slice(1);
    byId(`monitor${key}Warning`).value = String(config[`${resource}_warning`] ?? "");
    byId(`monitor${key}Critical`).value = String(config[`${resource}_critical`] ?? "");
  });
}

function storeNotificationPreference(enabled) {
  state.notificationsEnabled = Boolean(enabled);
  try {
    window.localStorage.setItem("hermes.notifications.enabled", enabled ? "1" : "0");
  } catch {
    // O recurso continua funcionando durante a sessão mesmo sem localStorage.
  }
  updateNotificationButton();
}

function loadNotificationPreference() {
  let wanted = false;
  try {
    wanted = window.localStorage.getItem("hermes.notifications.enabled") === "1";
  } catch {
    wanted = false;
  }
  state.notificationsEnabled = Boolean(
    wanted && "Notification" in window && window.Notification.permission === "granted",
  );
  updateNotificationButton();
}

function updateNotificationButton() {
  const button = byId("enableNotifications");
  if (!button) return;
  if (!("Notification" in window)) {
    button.disabled = true;
    button.textContent = "Avisos indisponíveis";
    return;
  }
  button.disabled = false;
  button.replaceChildren(icon("bell"));
  if (window.Notification.permission === "denied") {
    button.append(" Avisos bloqueados");
    button.disabled = true;
  } else if (state.notificationsEnabled) {
    button.append(" Avisos ativos");
    button.classList.add("is-active");
  } else {
    button.append(" Ativar avisos");
    button.classList.remove("is-active");
  }
}

async function toggleNotifications() {
  if (!("Notification" in window)) return;
  if (state.notificationsEnabled) {
    storeNotificationPreference(false);
    showToast("Avisos pausados", "Os alertas continuarão aparecendo dentro do HERMES.");
    return;
  }
  try {
    const permission = await window.Notification.requestPermission();
    storeNotificationPreference(permission === "granted");
    if (permission === "granted") {
      showToast("Avisos do Windows ativados", "Novos alertas confirmados poderão aparecer fora da janela.");
    } else {
      showToast("Permissão não concedida", "Você ainda verá todos os alertas dentro do HERMES.", true);
    }
  } catch (error) {
    showToast("Avisos indisponíveis", error.message, true);
  }
}

function notifyMonitorAlert(alert) {
  if (!state.notificationsEnabled || !("Notification" in window)) return;
  if (window.Notification.permission !== "granted") {
    storeNotificationPreference(false);
    return;
  }
  const notification = new window.Notification(
    alert.severity === "critical" ? "HERMES • Alerta crítico" : "HERMES • Atenção",
    { body: alert.message, tag: `hermes-monitor-${alert.id}`, renotify: false },
  );
  notification.onclick = () => {
    window.focus();
    navigate("monitor");
    notification.close();
  };
}

function renderMonitorAlerts(alerts = [], summary = {}) {
  const list = byId("monitorAlertsList");
  list.replaceChildren();
  const active = alerts.filter((alert) => alert.status === "active");
  const unacknowledged = alerts.filter((alert) => !alert.acknowledged);
  byId("monitorAlertCount").textContent = String(active.length);
  byId("monitorAlertCount").classList.toggle("has-alerts", active.length > 0);
  byId("monitorAlertsSummary").textContent = alerts.length
    ? `${active.length} ativos • ${summary.unacknowledged_alerts ?? unacknowledged.length} não vistos • ${alerts.length} exibidos`
    : "Nenhum alerta registrado";
  byId("acknowledgeAllAlerts").disabled = unacknowledged.length === 0;
  byId("clearMonitorHistory").disabled = alerts.length === 0 && !Number(summary.sample_count);

  if (state.monitorAlertsReady) {
    active.filter((alert) => !alert.acknowledged && !state.monitorAlertIds.has(alert.id)).forEach((alert) => {
      showToast(alert.severity === "critical" ? "Alerta crítico" : "Alerta de atenção", alert.message, true);
      notifyMonitorAlert(alert);
    });
  }
  alerts.forEach((alert) => state.monitorAlertIds.add(alert.id));
  state.monitorAlertsReady = true;

  if (!alerts.length) {
    const empty = makeElement("div", "empty-state");
    const emptyIcon = makeElement("span", "empty-icon");
    emptyIcon.appendChild(icon("bell"));
    empty.append(emptyIcon, makeElement("strong", "", "Ambiente sem alertas"), makeElement("p", "", "Os eventos confirmados aparecerão aqui."));
    list.appendChild(empty);
    return;
  }

  alerts.forEach((alert) => {
    const card = makeElement("article", "monitor-alert-card");
    card.dataset.severity = alert.severity;
    card.dataset.status = alert.status;
    const marker = makeElement("span", "monitor-alert-marker");
    marker.appendChild(icon(alert.status === "resolved" ? "check" : "bell"));
    const copy = makeElement("div", "monitor-alert-copy");
    const heading = makeElement("div", "monitor-alert-card-heading");
    const headingText = makeElement("div");
    headingText.append(makeElement("strong", "", alert.title), makeElement("span", "", formatDate(alert.detected_at)));
    const badges = makeElement("div", "monitor-alert-badges");
    badges.appendChild(severityBadge(alert.severity));
    badges.appendChild(makeElement("span", `monitor-alert-state is-${alert.status}`, alert.status === "active" ? "Ativo" : "Resolvido"));
    if (alert.acknowledged) badges.appendChild(makeElement("span", "monitor-alert-state is-seen", "Visto"));
    heading.append(headingText, badges);
    const message = makeElement("p", "", alert.message);
    const meta = makeElement("div", "monitor-alert-meta");
    meta.append(
      makeElement("span", "", `Atual ${Number(alert.last_value).toFixed(1)}%`),
      makeElement("span", "", `Pico ${Number(alert.peak_value).toFixed(1)}%`),
      makeElement("span", "", `${alert.occurrences} ocorrências`),
    );
    copy.append(heading, message, meta);
    card.append(marker, copy);
    const actions = makeElement("div", "monitor-alert-actions");
    const linkedIncident = state.incidents.find(
      (incident) => incident.monitor_alert_id === alert.id && incident.status !== "resolved",
    );
    const incidentButton = makeElement(
      "button",
      "button button-secondary button-compact",
      linkedIncident ? "Ver incidente" : "Abrir incidente",
    );
    incidentButton.type = "button";
    incidentButton.addEventListener("click", () => {
      if (linkedIncident) {
        state.activeIncidentId = linkedIncident.id;
        navigate("incidents");
        openIncident(linkedIncident.id);
      } else {
        createIncidentFromAlert(alert.id);
      }
    });
    actions.appendChild(incidentButton);
    if (!alert.acknowledged) {
      const button = makeElement("button", "button button-ghost button-compact", "Marcar como visto");
      button.type = "button";
      button.addEventListener("click", () => acknowledgeMonitorAlerts(alert.id));
      actions.appendChild(button);
    }
    card.appendChild(actions);
    list.appendChild(card);
  });
}

function syncMonitorPolling(running) {
  if (running && !state.monitorPollId) {
    state.monitorPollId = window.setInterval(() => {
      if (!document.hidden) refreshMonitor(true);
    }, 5000);
  } else if (!running && state.monitorPollId) {
    window.clearInterval(state.monitorPollId);
    state.monitorPollId = null;
  }
}

function renderMonitor(data) {
  state.monitorData = data;
  const runtime = data.runtime || {};
  const config = data.config || {};
  const summary = data.summary || {};
  const latest = data.latest;
  const running = Boolean(runtime.running);
  updateMonitorStatus(runtime);
  syncMonitorPolling(running);
  populateMonitorConfig(config);

  byId("startMonitor").hidden = running;
  byId("startMonitor").disabled = runtime.available === false;
  byId("stopMonitor").hidden = !running;
  const stateCard = byId("monitorStateCard");
  stateCard.dataset.state = runtime.available === false ? "error" : running ? "running" : "stopped";
  byId("monitorStateTitle").textContent = runtime.available === false
    ? "Telemetria indisponível"
    : running ? "Monitor em execução" : "Monitor parado";
  byId("monitorStateText").textContent = runtime.last_error
    ? runtime.last_error
    : running
      ? `Coleta a cada ${config.interval_seconds} segundos; alerta após ${config.consecutive_samples} leituras.`
      : "Ative quando quiser registrar o histórico local.";
  byId("monitorLastSample").textContent = latest ? formatDate(latest.recorded_at) : "—";
  byId("monitorSampleCount").textContent = Number(summary.sample_count || 0).toLocaleString("pt-BR");
  byId("monitorStorage").textContent = formatBytes(data.storage_bytes || 0);

  ["cpu", "memory", "disk"].forEach((resource) => updateMonitorResource(resource, latest, summary, config));
  byId("monitorNetworkUp").textContent = latest ? formatRate(latest.network_sent_bps) : "—";
  byId("monitorNetworkDown").textContent = latest ? formatRate(latest.network_received_bps) : "—";
  const samples = data.samples || [];
  byId("monitorChartRange").textContent = samples.length
    ? `${samples.length} coletas • ${formatDate(samples[0].recorded_at)} até ${formatDate(samples[samples.length - 1].recorded_at)}`
    : "Aguardando a primeira coleta";
  drawMonitorChart(samples);
  renderMonitorAlerts(data.alerts || [], summary);
}

async function refreshMonitor(silent = true) {
  if (state.monitorRefreshing) return state.monitorData;
  state.monitorRefreshing = true;
  try {
    const data = await api("/api/monitor?sample_limit=180&alert_limit=100");
    renderMonitor(data);
    return data;
  } catch (error) {
    updateMonitorStatus({ available: false, running: false });
    byId("monitorStateCard").dataset.state = "error";
    byId("monitorStateTitle").textContent = "Monitor indisponível";
    byId("monitorStateText").textContent = error.message;
    if (!silent) showToast("Monitor indisponível", error.message, true);
    return null;
  } finally {
    state.monitorRefreshing = false;
  }
}

async function startMonitor() {
  const button = byId("startMonitor");
  button.disabled = true;
  try {
    const data = await api("/api/monitor/start", { method: "POST", body: "{}" });
    renderMonitor(data);
    showToast("Monitoramento iniciado", "A primeira coleta está sendo registrada localmente.");
  } catch (error) {
    showToast("Não foi possível iniciar", error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function stopMonitor() {
  const button = byId("stopMonitor");
  button.disabled = true;
  try {
    const data = await api("/api/monitor/stop", { method: "POST", body: "{}" });
    renderMonitor(data);
    showToast("Monitoramento pausado", "O histórico existente foi preservado.");
  } catch (error) {
    showToast("Não foi possível pausar", error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function saveMonitorConfiguration(event) {
  event.preventDefault();
  const button = byId("saveMonitorConfig");
  const payload = {
    interval_seconds: Number(byId("monitorInterval").value),
    consecutive_samples: Number(byId("monitorConsecutive").value),
    retention_hours: Number(byId("monitorRetention").value),
    cpu_warning: Number(byId("monitorCpuWarning").value),
    cpu_critical: Number(byId("monitorCpuCritical").value),
    memory_warning: Number(byId("monitorMemoryWarning").value),
    memory_critical: Number(byId("monitorMemoryCritical").value),
    disk_warning: Number(byId("monitorDiskWarning").value),
    disk_critical: Number(byId("monitorDiskCritical").value),
  };
  button.disabled = true;
  try {
    const data = await api("/api/monitor/config", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.monitorConfigDirty = false;
    renderMonitor(data);
    showToast("Limites atualizados", "As novas regras serão usadas nas próximas coletas.");
  } catch (error) {
    showToast("Configuração inválida", error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function acknowledgeMonitorAlerts(alertId = null) {
  try {
    await api("/api/monitor/alerts/acknowledge", {
      method: "POST",
      body: JSON.stringify(alertId ? { alert_id: alertId } : {}),
    });
    await refreshMonitor(true);
    showToast("Alertas revisados", alertId ? "O alerta foi marcado como visto." : "Todos os alertas foram marcados como vistos.");
  } catch (error) {
    showToast("Não foi possível atualizar", error.message, true);
  }
}

async function clearMonitorHistory() {
  const confirmed = window.confirm("Apagar todas as coletas e alertas do monitor? As configurações serão preservadas.");
  if (!confirmed) return;
  try {
    const result = await api("/api/monitor/history", { method: "DELETE" });
    state.monitorAlertsReady = false;
    await refreshMonitor(true);
    showToast("Histórico removido", `${result.samples_deleted} coletas e ${result.alerts_deleted} alertas apagados.`);
  } catch (error) {
    showToast("Não foi possível limpar", error.message, true);
  }
}

function exportMonitorData() {
  if (!state.monitorData) {
    showToast("Sem dados", "Atualize o monitor antes de exportar.", true);
    return;
  }
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  downloadJson(`hermes-monitor-${stamp}.json`, {
    exported_at: new Date().toISOString(),
    config: state.monitorData.config,
    summary: state.monitorData.summary,
    samples: state.monitorData.samples,
    alerts: state.monitorData.alerts,
  });
  showToast("Dados exportados", "O histórico exibido foi salvo em JSON.");
}

function incidentStateBadge(status) {
  const safeStatus = Object.hasOwn(incidentStatusLabels, status) ? status : "open";
  return makeElement(
    "span",
    `incident-state-badge is-${safeStatus}`,
    incidentStatusLabels[safeStatus],
  );
}

function renderIncidentSummary(summary = {}) {
  state.incidentSummary = summary;
  byId("incidentOpenCount").textContent = String(summary.open || 0);
  byId("incidentInvestigatingCount").textContent = String(summary.investigating || 0);
  byId("incidentCriticalCount").textContent = String(summary.critical_active || 0);
  byId("incidentResolvedCount").textContent = String(summary.resolved || 0);
  byId("incidentCount").textContent = String(summary.active || 0);
  byId("incidentCount").classList.toggle("has-alerts", Number(summary.active || 0) > 0);
}

function renderIncidentList(incidents = []) {
  state.incidents = incidents;
  const list = byId("incidentList");
  list.replaceChildren();
  if (!incidents.length) {
    const empty = makeElement("div", "empty-state");
    const emptyIcon = makeElement("span", "empty-icon");
    emptyIcon.appendChild(icon("shield"));
    empty.append(
      emptyIcon,
      makeElement("strong", "", "Nenhum incidente neste filtro"),
      makeElement("p", "", "Abra um alerta do monitor ou registre uma observação manual."),
    );
    list.appendChild(empty);
    return;
  }
  incidents.forEach((incident) => {
    const button = makeElement("button", "incident-list-item");
    button.type = "button";
    button.dataset.severity = incident.severity;
    button.dataset.status = incident.status;
    button.classList.toggle("is-active", incident.id === state.activeIncidentId);
    const heading = makeElement("div", "incident-list-item-heading");
    heading.append(makeElement("strong", "", incident.title), incidentStateBadge(incident.status));
    const description = makeElement("p", "", incident.description || "Sem descrição adicional.");
    const meta = makeElement("div", "incident-list-item-meta");
    meta.append(
      makeElement("span", "", severityLabels[incident.severity] || "Atenção"),
      makeElement("span", "", formatDate(incident.updated_at)),
    );
    button.append(heading, description, meta);
    button.addEventListener("click", () => openIncident(incident.id));
    list.appendChild(button);
  });
}

async function refreshIncidents(silent = true) {
  if (state.incidentsRefreshing) return null;
  state.incidentsRefreshing = true;
  const status = byId("incidentStatusFilter")?.value || "";
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  try {
    const data = await api(`/api/incidents${query}`);
    renderIncidentSummary(data.summary || {});
    renderIncidentList(data.incidents || []);
    if (state.monitorData) {
      renderMonitorAlerts(state.monitorData.alerts || [], state.monitorData.summary || {});
    }
    return data;
  } catch (error) {
    if (!silent) showToast("Incidentes indisponíveis", error.message, true);
    return null;
  } finally {
    state.incidentsRefreshing = false;
  }
}

function snapshotValue(incident, resource) {
  const snapshot = incident.snapshot || {};
  const sample = snapshot.monitor_sample || {};
  const metrics = snapshot.metrics || {};
  const nested = metrics[resource] || {};
  const value = sample[`${resource}_percent`] ?? nested.percent;
  return Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)}%` : "—";
}

function snapshotItem(label, value) {
  const item = makeElement("div", "incident-snapshot-item");
  item.append(makeElement("span", "", label), makeElement("strong", "", value || "—"));
  return item;
}

function renderIncidentDetail(incident) {
  state.activeIncidentId = incident.id;
  renderIncidentList(state.incidents);
  const detail = byId("incidentDetail");
  detail.replaceChildren();

  const header = makeElement("div", "incident-detail-header");
  const title = makeElement("div", "incident-detail-title");
  title.append(
    makeElement("span", "panel-label", incident.source_type === "monitor" ? "Alerta do monitor" : "Registro manual"),
    makeElement("h2", "", incident.title),
    makeElement("p", "", `Criado em ${formatDate(incident.created_at)} • atualizado em ${formatDate(incident.updated_at)}`),
  );
  const tools = makeElement("div", "incident-detail-tools");
  const badges = makeElement("div", "incident-detail-badges");
  badges.append(severityBadge(incident.severity), incidentStateBadge(incident.status));
  const actions = makeElement("div", "incident-detail-actions");

  if (incident.status !== "investigating") {
    const investigate = makeElement("button", "button button-ghost button-compact", incident.status === "resolved" ? "Reabrir" : "Investigar");
    investigate.type = "button";
    investigate.addEventListener("click", () => updateIncidentStatus(
      incident.id,
      incident.status === "resolved" ? "open" : "investigating",
    ));
    actions.appendChild(investigate);
  }
  if (incident.status !== "resolved") {
    const resolve = makeElement("button", "button button-secondary button-compact", "Resolver");
    resolve.type = "button";
    resolve.addEventListener("click", () => updateIncidentStatus(incident.id, "resolved"));
    actions.appendChild(resolve);
  }
  const htmlLink = makeElement("a", "button button-ghost button-compact", "HTML");
  htmlLink.href = `/api/incidents/${encodeURIComponent(incident.id)}/html`;
  htmlLink.download = "";
  const pdfLink = makeElement("a", "button button-ghost button-compact", "PDF");
  pdfLink.href = `/api/incidents/${encodeURIComponent(incident.id)}/pdf`;
  pdfLink.download = "";
  actions.append(htmlLink, pdfLink);
  tools.append(badges, actions);
  header.append(title, tools);

  const body = makeElement("div", "incident-detail-body");
  const description = makeElement("section", "incident-description");
  description.append(
    makeElement("h3", "", "Descrição"),
    makeElement("p", "", incident.description || "Sem descrição adicional."),
  );

  const snapshot = makeElement("section", "incident-section");
  const snapshotHeading = makeElement("div", "incident-section-heading");
  snapshotHeading.append(
    makeElement("div", "", ""),
  );
  snapshotHeading.firstChild.append(
    makeElement("h3", "", "Snapshot local"),
    makeElement("p", "", `Capturado em ${formatDate(incident.snapshot?.captured_at)} sem listar processos ou arquivos.`),
  );
  const snapshotGrid = makeElement("div", "incident-snapshot-grid");
  snapshotGrid.append(
    snapshotItem("CPU", snapshotValue(incident, "cpu")),
    snapshotItem("Memória", snapshotValue(incident, "memory")),
    snapshotItem("Disco", snapshotValue(incident, "disk")),
    snapshotItem("Host", incident.snapshot?.system?.hostname || "—"),
  );
  snapshot.append(snapshotHeading, snapshotGrid);

  const checklist = makeElement("section", "incident-section");
  const checklistHeading = makeElement("div", "incident-section-heading");
  const completed = (incident.checklist || []).filter((item) => item.completed).length;
  const checklistCopy = makeElement("div");
  checklistCopy.append(
    makeElement("h3", "", "Checklist defensivo"),
    makeElement("p", "", `${completed} de ${(incident.checklist || []).length} etapas concluídas • somente leitura`),
  );
  checklistHeading.appendChild(checklistCopy);
  const checklistList = makeElement("div", "incident-checklist");
  (incident.checklist || []).forEach((item) => {
    const label = makeElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = Boolean(item.completed);
    checkbox.disabled = incident.status === "resolved";
    checkbox.addEventListener("change", () => setIncidentChecklist(
      incident.id,
      item.id,
      checkbox.checked,
      checkbox,
    ));
    label.append(checkbox, makeElement("span", "", item.label));
    checklistList.appendChild(label);
  });
  checklist.append(checklistHeading, checklistList);

  const notes = makeElement("section", "incident-section");
  const noteHeading = makeElement("div", "incident-section-heading");
  const noteCopy = makeElement("div");
  noteCopy.append(makeElement("h3", "", "Registrar evidência"), makeElement("p", "", "Adicione uma observação curta à linha do tempo."));
  noteHeading.appendChild(noteCopy);
  const noteForm = makeElement("form", "incident-note-form");
  const noteInput = document.createElement("textarea");
  noteInput.maxLength = 12000;
  noteInput.placeholder = "O que foi verificado?";
  const noteButton = makeElement("button", "button button-secondary", "Adicionar nota");
  noteButton.type = "submit";
  noteForm.append(noteInput, noteButton);
  noteForm.addEventListener("submit", (event) => {
    event.preventDefault();
    addIncidentNote(incident.id, noteInput.value, noteButton);
  });
  notes.append(noteHeading, noteForm);

  const timeline = makeElement("section", "incident-section");
  const timelineHeading = makeElement("div", "incident-section-heading");
  const timelineCopy = makeElement("div");
  timelineCopy.append(
    makeElement("h3", "", "Linha do tempo"),
    makeElement("p", "", `${(incident.timeline || []).length} eventos preservados localmente.`),
  );
  const analyze = makeElement("button", "button button-secondary button-compact", "Analisar com IA");
  analyze.type = "button";
  analyze.prepend(icon("brain"));
  analyze.addEventListener("click", () => analyzeIncident(incident.id, analyze));
  timelineHeading.append(timelineCopy, analyze);
  const timelineList = makeElement("div", "incident-timeline");
  const eventLabels = { created: "Criação", status: "Estado", note: "Nota", checklist: "Checklist", analysis: "Análise da IA" };
  (incident.timeline || []).slice().reverse().forEach((event) => {
    const entry = makeElement("article", "incident-event");
    entry.dataset.type = event.type;
    entry.append(
      makeElement("span", "", `${eventLabels[event.type] || "Evento"} • ${formatDate(event.created_at)}`),
      makeElement("p", "", event.message),
    );
    timelineList.appendChild(entry);
  });
  timeline.append(timelineHeading, timelineList);

  const deleteRow = makeElement("div", "incident-detail-actions");
  const remove = makeElement("button", "button button-ghost button-compact danger-text", "Excluir incidente");
  remove.type = "button";
  remove.addEventListener("click", () => deleteIncident(incident));
  deleteRow.appendChild(remove);

  body.append(description, snapshot, checklist, notes, timeline, deleteRow);
  detail.append(header, body);
}

async function openIncident(incidentId) {
  try {
    const data = await api(`/api/incidents/${encodeURIComponent(incidentId)}`);
    renderIncidentDetail(data.incident);
  } catch (error) {
    showToast("Incidente indisponível", error.message, true);
  }
}

async function updateIncidentStatus(incidentId, status) {
  try {
    const data = await api(`/api/incidents/${encodeURIComponent(incidentId)}/status`, {
      method: "POST",
      body: JSON.stringify({ status }),
    });
    renderIncidentDetail(data.incident);
    await Promise.all([refreshIncidents(true), refreshMonitor(true)]);
    showToast("Estado atualizado", `Incidente marcado como ${incidentStatusLabels[status].toLowerCase()}.`);
  } catch (error) {
    showToast("Estado não atualizado", error.message, true);
  }
}

async function setIncidentChecklist(incidentId, itemId, completed, checkbox) {
  checkbox.disabled = true;
  try {
    const data = await api(
      `/api/incidents/${encodeURIComponent(incidentId)}/checklist/${encodeURIComponent(itemId)}`,
      { method: "POST", body: JSON.stringify({ completed }) },
    );
    renderIncidentDetail(data.incident);
    await refreshIncidents(true);
  } catch (error) {
    checkbox.checked = !completed;
    checkbox.disabled = false;
    showToast("Checklist não atualizado", error.message, true);
  }
}

async function addIncidentNote(incidentId, message, button) {
  if (!message.trim()) return;
  button.disabled = true;
  try {
    const data = await api(`/api/incidents/${encodeURIComponent(incidentId)}/note`, {
      method: "POST",
      body: JSON.stringify({ message }),
    });
    renderIncidentDetail(data.incident);
    await refreshIncidents(true);
    showToast("Nota registrada", "A observação entrou na linha do tempo local.");
  } catch (error) {
    button.disabled = false;
    showToast("Nota não registrada", error.message, true);
  }
}

async function analyzeIncident(incidentId, button) {
  button.disabled = true;
  button.textContent = "Analisando…";
  try {
    const data = await api(`/api/incidents/${encodeURIComponent(incidentId)}/analyze`, {
      method: "POST",
      body: "{}",
    });
    renderIncidentDetail(data.incident);
    await refreshIncidents(true);
    showToast("Análise concluída", "A interpretação da IA local foi adicionada à linha do tempo.");
  } catch (error) {
    button.disabled = false;
    button.textContent = "Analisar com IA";
    showToast("Análise indisponível", error.message, true);
  }
}

async function createIncidentFromAlert(alertId) {
  try {
    const data = await api("/api/incidents/from-alert", {
      method: "POST",
      body: JSON.stringify({ alert_id: alertId }),
    });
    state.activeIncidentId = data.incident.id;
    await refreshIncidents(true);
    navigate("incidents");
    renderIncidentDetail(data.incident);
    showToast(
      data.incident.duplicate ? "Incidente já aberto" : "Incidente criado",
      data.incident.duplicate ? "Abrimos o registro ativo vinculado a este alerta." : "Snapshot e checklist foram registrados localmente.",
    );
  } catch (error) {
    showToast("Incidente não criado", error.message, true);
  }
}

function showIncidentDialog() {
  const dialog = byId("incidentCreateDialog");
  byId("incidentCreateForm").reset();
  if (typeof dialog.showModal === "function") dialog.showModal();
  else dialog.setAttribute("open", "");
  window.setTimeout(() => byId("incidentTitle").focus(), 30);
}

function closeIncidentDialog() {
  const dialog = byId("incidentCreateDialog");
  if (typeof dialog.close === "function") dialog.close();
  else dialog.removeAttribute("open");
}

async function createManualIncident(event) {
  event.preventDefault();
  const button = byId("saveIncident");
  button.disabled = true;
  try {
    const data = await api("/api/incidents", {
      method: "POST",
      body: JSON.stringify({
        title: byId("incidentTitle").value,
        severity: byId("incidentSeverity").value,
        description: byId("incidentDescription").value,
      }),
    });
    closeIncidentDialog();
    state.activeIncidentId = data.incident.id;
    await refreshIncidents(true);
    renderIncidentDetail(data.incident);
    navigate("incidents");
    showToast("Incidente criado", "O snapshot atual e o checklist foram registrados.");
  } catch (error) {
    showToast("Incidente não criado", error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function deleteIncident(incident) {
  if (!window.confirm(`Excluir permanentemente o incidente “${incident.title}”?`)) return;
  try {
    await api(`/api/incidents/${encodeURIComponent(incident.id)}`, { method: "DELETE" });
    state.activeIncidentId = null;
    byId("incidentDetail").replaceChildren();
    const empty = makeElement("div", "empty-state incident-detail-empty");
    const emptyIcon = makeElement("span", "empty-icon");
    emptyIcon.appendChild(icon("shield"));
    empty.append(emptyIcon, makeElement("strong", "", "Incidente excluído"), makeElement("p", "", "Selecione outro registro na lista."));
    byId("incidentDetail").appendChild(empty);
    await Promise.all([refreshIncidents(true), refreshMonitor(true)]);
    showToast("Incidente excluído", "O registro e sua linha do tempo foram removidos.");
  } catch (error) {
    showToast("Incidente não excluído", error.message, true);
  }
}

function exportBackup() {
  const link = document.createElement("a");
  link.href = "/api/backup";
  link.download = "";
  document.body.appendChild(link);
  link.click();
  link.remove();
  showToast("Backup solicitado", "O ZIP está sendo preparado com os dados locais.");
}

function fileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Não foi possível ler o arquivo selecionado."));
    reader.onload = () => {
      const value = String(reader.result || "");
      resolve(value.includes(",") ? value.split(",", 2)[1] : value);
    };
    reader.readAsDataURL(file);
  });
}

async function restoreBackup(file) {
  if (!file) return;
  if (file.size > 96 * 1024 * 1024) {
    showToast("Backup muito grande", "O limite de restauração é 96 MB.", true);
    return;
  }
  const confirmed = window.confirm(
    "Restaurar este backup? Arquivos com o mesmo nome serão substituídos após a validação. Modelos e executáveis não serão alterados.",
  );
  if (!confirmed) return;
  const button = byId("importBackup");
  button.disabled = true;
  byId("backupStatus").textContent = "Validando e restaurando o ZIP local…";
  try {
    const archiveBase64 = await fileAsBase64(file);
    const data = await api("/api/backup/restore", {
      method: "POST",
      body: JSON.stringify({ archive_base64: archiveBase64 }),
    });
    byId("backupStatus").textContent = `${data.restored_count} arquivos restaurados. Recarregando o HERMES…`;
    showToast("Backup restaurado", "A interface será recarregada para abrir os dados restaurados.");
    window.setTimeout(() => window.location.reload(), 900);
  } catch (error) {
    button.disabled = false;
    byId("backupStatus").textContent = "Nenhum dado foi alterado quando a validação falha.";
    showToast("Restauração cancelada", error.message, true);
  } finally {
    byId("backupFileInput").value = "";
  }
}

function findingsByPriority(findings) {
  const priority = { critical: 0, attention: 1, normal: 2 };
  return [...(findings || [])].sort((a, b) => (priority[a.severity] ?? 3) - (priority[b.severity] ?? 3));
}

function renderAlerts(findings) {
  const table = byId("alertsTable");
  table.replaceChildren();
  const sorted = findingsByPriority(findings).slice(0, 4);
  if (!sorted.length) {
    const row = makeElement("tr", "empty-row");
    const cell = makeElement("td", "", "Nenhum achado disponível neste relatório.");
    cell.colSpan = 4;
    row.appendChild(cell);
    table.appendChild(row);
    byId("alertsSummary").textContent = "Nenhum alerta encontrado";
    return;
  }

  sorted.forEach((finding) => {
    const row = document.createElement("tr");
    const serviceCell = document.createElement("td");
    const service = makeElement("div", "service-cell");
    service.append(makeElement("span", "service-marker"), document.createTextNode(finding.service || "Serviço"));
    serviceCell.appendChild(service);
    const severityCell = document.createElement("td");
    severityCell.appendChild(severityBadge(finding.severity));
    const messageCell = makeElement("td", "", finding.title || finding.message || "Achado técnico");
    const dateCell = makeElement("td", "", formatTime(finding.detected_at));
    row.append(serviceCell, severityCell, messageCell, dateCell);
    table.appendChild(row);
  });
  const alertCount = findings.filter((item) => item.severity !== "normal").length;
  byId("alertsSummary").textContent = alertCount
    ? `${alertCount} ${alertCount === 1 ? "alerta encontrado" : "alertas encontrados"}`
    : "Todas as verificações estão normais";
}

function renderLatest(report) {
  const empty = byId("latestEmpty");
  const content = byId("latestContent");
  if (!report) {
    empty.hidden = false;
    content.hidden = true;
    state.latestFilename = null;
    renderAlerts([]);
    return;
  }
  state.latestFilename = report.filename;
  empty.hidden = true;
  content.hidden = false;
  byId("latestType").textContent = diagnosticLabel(report.type);
  byId("latestDate").textContent = formatDate(report.completed_at);
  byId("latestDuration").textContent = formatDuration(report.duration_seconds);
  byId("latestChecks").textContent = report.summary?.checks ?? report.findings?.length ?? "—";
  byId("latestAlerts").textContent = report.summary?.alerts ?? 0;
  renderAlerts(report.findings || []);
}

function renderReportsList(reports) {
  const list = byId("reportsList");
  list.replaceChildren();
  byId("reportCount").textContent = String(reports.length);
  byId("reportsTotal").textContent = `${reports.length} ${reports.length === 1 ? "arquivo" : "arquivos"}`;
  if (!reports.length) {
    const empty = makeElement("div", "empty-state");
    const emptyIcon = makeElement("span", "empty-icon");
    emptyIcon.appendChild(icon("report"));
    empty.append(emptyIcon, makeElement("strong", "", "Nenhum relatório encontrado"), makeElement("p", "", "Os próximos diagnósticos aparecerão aqui."));
    list.appendChild(empty);
    return;
  }

  reports.forEach((report) => {
    const button = makeElement("button", "report-list-item");
    button.type = "button";
    button.dataset.filename = report.filename;
    if (report.filename === state.activeReport) button.classList.add("is-active");
    if (report.filename === state.baselineFilename) button.classList.add("is-baseline");
    const reportIcon = makeElement("span", "report-list-icon");
    reportIcon.appendChild(icon("report"));
    const copy = makeElement("span", "report-list-copy");
    copy.append(
      makeElement("strong", "", diagnosticLabel(report.type)),
      makeElement("span", "", formatDate(report.completed_at)),
    );
    if (report.filename === state.baselineFilename) {
      copy.appendChild(makeElement("small", "baseline-label", "Referência fixada"));
    }
    const alerts = Number(report.summary?.alerts || 0);
    const count = makeElement("span", `report-alert-count${alerts ? "" : " is-clear"}`, alerts);
    count.title = alerts ? `${alerts} alertas` : "Sem alertas";
    button.append(reportIcon, copy, count);
    button.addEventListener("click", () => openReport(report.filename));
    list.appendChild(button);
  });
}

function reportOptionLabel(report) {
  return `${diagnosticLabel(report.type)} — ${formatDate(report.completed_at)}`;
}

function fillReportSelect(select, reports, selectedFilename) {
  select.replaceChildren();
  const placeholder = makeElement("option", "", "Selecione um relatório");
  placeholder.value = "";
  select.appendChild(placeholder);
  reports.forEach((report) => {
    const option = makeElement("option", "", reportOptionLabel(report));
    option.value = report.filename;
    option.title = report.filename;
    select.appendChild(option);
  });
  if (reports.some((report) => report.filename === selectedFilename)) {
    select.value = selectedFilename;
  }
}

function comparisonIsReady() {
  const baseline = byId("baselineReportSelect").value;
  const current = byId("currentReportSelect").value;
  return Boolean(baseline && current && baseline !== current);
}

function updateComparisonAvailability() {
  const ready = comparisonIsReady();
  byId("runReportComparison").disabled = !ready;
  byId("saveBaselineReport").disabled = !byId("baselineReportSelect").value;
  byId("analyzeReportComparison").disabled = !ready || !state.lastComparison;
  const help = byId("comparisonHelp");
  if (state.reports.length < 2) {
    help.textContent = "Execute pelo menos dois diagnósticos para medir a evolução.";
  } else if (!ready) {
    help.textContent = "Escolha relatórios diferentes para referência e estado atual.";
  } else if (state.baselineFilename) {
    help.textContent = "Referência fixada. A comparação principal funciona sem IA e não altera o computador.";
  } else {
    help.textContent = "A comparação principal funciona sem IA e não altera o computador.";
  }
}

function updateComparisonSelectors() {
  const baselineSelect = byId("baselineReportSelect");
  const currentSelect = byId("currentReportSelect");
  const previousBaseline = baselineSelect.value;
  const previousCurrent = currentSelect.value;
  const filenames = new Set(state.reports.map((report) => report.filename));
  const baseline = filenames.has(previousBaseline)
    ? previousBaseline
    : filenames.has(state.baselineFilename)
      ? state.baselineFilename
      : state.reports[1]?.filename || state.reports[0]?.filename || "";
  const current = filenames.has(previousCurrent) && previousCurrent !== baseline
    ? previousCurrent
    : state.reports.find((report) => report.filename !== baseline)?.filename || "";
  fillReportSelect(baselineSelect, state.reports, baseline);
  fillReportSelect(currentSelect, state.reports, current);
  updateComparisonAvailability();
}

async function refreshReports() {
  try {
    const data = await api("/api/reports");
    state.reports = data.reports || [];
    state.baselineFilename = data.baseline?.filename || null;
    renderReportsList(state.reports);
    renderLatest(state.reports[0] || null);
    updateComparisonSelectors();
    updateKnowledgeReportOptions();
    return state.reports;
  } catch (error) {
    showToast("Relatórios indisponíveis", error.message, true);
    return [];
  }
}

function findingCard(finding) {
  const severity = Object.hasOwn(severityLabels, finding.severity) ? finding.severity : "attention";
  const card = makeElement("article", "finding-card");
  card.dataset.severity = severity;
  const head = makeElement("div", "finding-head");
  head.append(makeElement("strong", "", finding.title || finding.service || "Achado"), severityBadge(severity));
  card.append(head, makeElement("p", "", finding.message || "Sem detalhes adicionais."));
  if (finding.evidence) {
    const details = makeElement("details", "finding-evidence");
    details.append(makeElement("summary", "", "Ver evidência coletada"), makeElement("pre", "", finding.evidence));
    card.appendChild(details);
  }
  return card;
}

function reportStats(summary = {}, duration = null) {
  const stats = makeElement("div", "result-stats");
  const values = [
    ["Verificações", summary.checks ?? 0],
    ["Alertas", summary.alerts ?? 0],
    ["Críticos", summary.critical ?? 0],
    ["Duração", formatDuration(duration)],
  ];
  values.forEach(([label, value]) => {
    const item = makeElement("div", "result-stat");
    item.append(makeElement("span", "", label), makeElement("strong", "", value));
    stats.appendChild(item);
  });
  return stats;
}

function downloadJson(filename, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename || "hermes-report.json";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    showToast("Copiado", "Conteúdo copiado para a área de transferência.");
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
    showToast("Copiado", "Conteúdo copiado para a área de transferência.");
  }
}

function reportExportUrl(filename) {
  return `/api/reports/${encodeURIComponent(filename)}/html`;
}

function renderAIAnalysis(container, data) {
  container.hidden = false;
  container.replaceChildren();
  const header = makeElement("div", "ai-analysis-header");
  const title = makeElement("div");
  title.append(
    makeElement("span", "panel-label", "Leitura assistida"),
    makeElement("h3", "", "Análise do HERMES"),
  );
  const copy = makeElement("button", "button button-ghost button-compact");
  copy.type = "button";
  copy.append(icon("copy"), document.createTextNode(" Copiar"));
  copy.addEventListener("click", () => copyText(data.analysis));
  header.append(title, copy);
  container.append(
    header,
    makeElement("p", "ai-analysis-text", data.analysis),
    makeElement("small", "ai-analysis-meta", `${data.mode === "deep" ? "Análise profunda" : "Análise rápida"} • ${formatDuration(data.duration_seconds)}`),
  );
}

async function analyzeReport(filename, container, button) {
  if (!filename || !container) return;
  button.disabled = true;
  container.hidden = false;
  container.replaceChildren(makeElement("div", "analysis-loading", "Analisando o relatório local…"));
  state.coreBusy = true;
  setCoreState("working", "Analisando relatório", "Assistente IA");
  try {
    const data = await api("/api/reports/analyze", {
      method: "POST",
      body: JSON.stringify({ filename, mode: "deep" }),
    });
    renderAIAnalysis(container, data);
    setCoreState("ready", "Análise concluída", "Revise as recomendações");
  } catch (error) {
    container.replaceChildren(makeElement("p", "analysis-error", error.message));
    showToast("Análise não concluída", error.message, true);
    setCoreState("error", "Falha na análise", error.message);
  } finally {
    button.disabled = false;
    state.coreBusy = false;
  }
}

const comparisonStatusLabels = {
  stable: "Estável",
  improved: "Melhorou",
  worsened: "Piorou",
  mixed: "Resultado misto",
};

function comparisonChangeCard(change, category) {
  const paired = category === "worsened" || category === "improved";
  const before = paired ? change.before : category === "resolved" ? change : null;
  const after = paired ? change.after : category === "new" ? change : null;
  const finding = after || before || {};
  const card = makeElement("article", `comparison-change-card change-${category}`);
  const head = makeElement("div", "comparison-change-head");
  const heading = makeElement("div");
  heading.append(
    makeElement("span", "panel-label", finding.service || "Verificação"),
    makeElement("strong", "", finding.title || "Achado técnico"),
  );
  const transition = makeElement("div", "severity-transition");
  if (paired) {
    transition.append(
      severityBadge(before?.severity),
      makeElement("span", "", "→"),
      severityBadge(after?.severity),
    );
  } else {
    transition.appendChild(severityBadge(finding.severity));
  }
  head.append(heading, transition);
  card.append(head, makeElement("p", "", finding.message || "Sem detalhes adicionais."));
  return card;
}

function appendComparisonSection(container, title, category, values) {
  if (!values?.length) return;
  const section = makeElement("section", "comparison-change-section");
  const heading = makeElement("div", "comparison-section-heading");
  heading.append(makeElement("h4", "", title), makeElement("span", "", values.length));
  const list = makeElement("div", "comparison-change-list");
  values.forEach((change) => list.appendChild(comparisonChangeCard(change, category)));
  section.append(heading, list);
  container.appendChild(section);
}

function renderComparisonResult(data) {
  const comparison = data.comparison;
  const result = byId("comparisonResult");
  result.hidden = false;
  result.replaceChildren();
  const summary = comparison.summary || {};
  const heading = makeElement("div", "comparison-result-heading");
  const copy = makeElement("div");
  copy.append(
    makeElement("span", "panel-label", "Resultado da comparação"),
    makeElement("h3", "", `${diagnosticLabel(comparison.baseline?.type)} • ${formatDate(comparison.baseline?.completed_at)} → ${formatDate(comparison.current?.completed_at)}`),
  );
  heading.append(
    copy,
    makeElement(
      "span",
      `comparison-status status-${summary.status || "stable"}`,
      comparisonStatusLabels[summary.status] || "Comparado",
    ),
  );
  result.appendChild(heading);

  (comparison.warnings || []).forEach((warning) => {
    result.appendChild(makeElement("p", "comparison-warning", warning));
  });

  const stats = makeElement("div", "comparison-stats");
  [
    ["Novos", summary.new ?? 0, "negative"],
    ["Resolvidos", summary.resolved ?? 0, "positive"],
    ["Pioraram", summary.worsened ?? 0, "negative"],
    ["Melhoraram", summary.improved ?? 0, "positive"],
    ["Δ alertas", `${Number(summary.alert_delta || 0) > 0 ? "+" : ""}${summary.alert_delta ?? 0}`, Number(summary.alert_delta || 0) > 0 ? "negative" : Number(summary.alert_delta || 0) < 0 ? "positive" : "neutral"],
  ].forEach(([label, value, tone]) => {
    const stat = makeElement("div", `comparison-stat is-${tone}`);
    stat.append(makeElement("span", "", label), makeElement("strong", "", value));
    stats.appendChild(stat);
  });
  result.appendChild(stats);

  if (comparison.metrics?.length) {
    const metricsSection = makeElement("section", "comparison-metrics");
    metricsSection.appendChild(makeElement("h4", "", "Variação dos recursos"));
    const metricsGrid = makeElement("div", "comparison-metrics-grid");
    comparison.metrics.forEach((metric) => {
      const metricCard = makeElement("div", `comparison-metric metric-${metric.direction}`);
      const delta = Number(metric.delta || 0);
      metricCard.append(
        makeElement("span", "", metric.resource),
        makeElement("strong", "", `${metric.before}${metric.unit} → ${metric.after}${metric.unit}`),
        makeElement("small", "", `${delta > 0 ? "+" : ""}${delta}${metric.unit}`),
      );
      metricsGrid.appendChild(metricCard);
    });
    metricsSection.appendChild(metricsGrid);
    result.appendChild(metricsSection);
  }

  const changes = makeElement("div", "comparison-changes");
  appendComparisonSection(changes, "Novos alertas", "new", comparison.changes?.new);
  appendComparisonSection(changes, "Itens que pioraram", "worsened", comparison.changes?.worsened);
  appendComparisonSection(changes, "Alertas resolvidos", "resolved", comparison.changes?.resolved);
  appendComparisonSection(changes, "Itens que melhoraram", "improved", comparison.changes?.improved);
  if (!changes.childElementCount) {
    changes.appendChild(makeElement("p", "comparison-empty", "Nenhuma mudança de severidade foi encontrada."));
  }
  result.appendChild(changes);

  if (data.ai_analysis) {
    const analysis = makeElement("section", "ai-analysis-card comparison-ai");
    renderAIAnalysis(analysis, data.ai_analysis);
    result.appendChild(analysis);
  }
}

async function runReportComparison(useAI = false) {
  const baseline = byId("baselineReportSelect").value;
  const current = byId("currentReportSelect").value;
  if (!baseline || !current || baseline === current) {
    showToast("Comparação incompleta", "Escolha dois relatórios diferentes.", true);
    return;
  }
  const compareButton = byId("runReportComparison");
  const aiButton = byId("analyzeReportComparison");
  compareButton.disabled = true;
  aiButton.disabled = true;
  const result = byId("comparisonResult");
  if (!useAI) {
    result.hidden = false;
    result.replaceChildren(makeElement("div", "analysis-loading", "Comparando as duas coletas…"));
  }
  state.coreBusy = true;
  setCoreState("working", useAI ? "Interpretando evolução" : "Comparando relatórios", "Diagnóstico inteligente");
  try {
    const data = await api("/api/reports/compare", {
      method: "POST",
      body: JSON.stringify({ baseline, current, use_ai: useAI }),
    });
    state.lastComparison = { baseline, current };
    renderComparisonResult(data);
    setCoreState("ready", "Comparação concluída", comparisonStatusLabels[data.comparison?.summary?.status] || "Resultado disponível");
    showToast(
      useAI ? "Interpretação concluída" : "Comparação concluída",
      useAI ? "A IA local explicou as mudanças encontradas." : "As mudanças foram calculadas sem depender da IA.",
    );
  } catch (error) {
    if (!useAI) result.replaceChildren(makeElement("p", "analysis-error", error.message));
    showToast("Comparação não concluída", error.message, true);
    setCoreState("error", "Falha na comparação", error.message);
  } finally {
    state.coreBusy = false;
    updateComparisonAvailability();
  }
}

async function saveBaseline(filename, button = null) {
  if (!filename) return;
  if (button) button.disabled = true;
  try {
    const data = await api("/api/reports/baseline", {
      method: "POST",
      body: JSON.stringify({ filename }),
    });
    state.baselineFilename = data.baseline?.filename || filename;
    renderReportsList(state.reports);
    byId("baselineReportSelect").value = state.baselineFilename;
    state.lastComparison = null;
    updateComparisonAvailability();
    if (button) {
      button.replaceChildren(icon("report"), document.createTextNode(" Referência fixada"));
    }
    showToast("Referência salva", "Este relatório será sugerido nas próximas comparações.");
  } catch (error) {
    showToast("Não foi possível fixar", error.message, true);
  } finally {
    if (button) button.disabled = false;
  }
}

function renderRemediationPlan(container, plan) {
  container.hidden = false;
  container.replaceChildren();
  const header = makeElement("div", "plan-heading");
  const title = makeElement("div");
  title.append(
    makeElement("span", "panel-label", "Plano local revisável"),
    makeElement("h3", "", "Próximos passos seguros"),
  );
  const counters = makeElement("div", "plan-counters");
  counters.append(
    makeElement("span", "", `${plan.summary?.tasks || 0} tarefas`),
    makeElement("span", "", `${plan.summary?.p1 || 0} P1`),
  );
  header.append(title, counters);
  container.append(header, makeElement("p", "plan-safety-notice", plan.safety_notice));

  if (!plan.tasks?.length) {
    container.appendChild(makeElement("div", "plan-empty", "Nenhum alerta exige plano de correção neste relatório."));
    return;
  }

  const tasks = makeElement("div", "plan-tasks");
  plan.tasks.forEach((task) => {
    const card = makeElement("article", "plan-task");
    const taskHead = makeElement("div", "plan-task-head");
    const taskTitle = makeElement("div");
    taskTitle.append(
      makeElement("span", "panel-label", `${task.id} • ${task.service}`),
      makeElement("h4", "", task.title),
    );
    taskHead.append(taskTitle, makeElement("span", `priority-badge priority-${task.priority.toLowerCase()}`, task.priority));
    card.append(taskHead, makeElement("p", "plan-reason", task.reason), makeElement("p", "plan-goal", task.goal));

    const steps = makeElement("ol", "plan-steps");
    (task.steps || []).forEach((step) => steps.appendChild(makeElement("li", "", step)));
    card.appendChild(steps);

    if (task.commands?.length) {
      const commands = makeElement("div", "plan-commands");
      commands.appendChild(makeElement("h5", "", "Verificações opcionais — somente leitura"));
      task.commands.forEach((item) => {
        const command = makeElement("div", "safe-command");
        const commandHead = makeElement("div", "safe-command-head");
        commandHead.append(
          makeElement("span", "", `${item.label} • ${item.platform}`),
          makeElement("span", "read-only-badge", "Somente leitura"),
        );
        const codeRow = makeElement("div", "safe-command-code");
        const code = makeElement("code", "", item.command);
        const copyButton = makeElement("button", "button button-ghost button-compact");
        copyButton.type = "button";
        copyButton.append(icon("copy"), document.createTextNode(" Copiar"));
        copyButton.addEventListener("click", () => copyText(item.command));
        codeRow.append(code, copyButton);
        command.append(commandHead, codeRow);
        commands.appendChild(command);
      });
      card.appendChild(commands);
    }

    const verification = makeElement("details", "plan-verification");
    verification.appendChild(makeElement("summary", "", "Como verificar depois"));
    const verificationList = makeElement("ul");
    (task.verification || []).forEach((item) => verificationList.appendChild(makeElement("li", "", item)));
    verification.appendChild(verificationList);
    card.appendChild(verification);
    tasks.appendChild(card);
  });
  container.appendChild(tasks);
}

async function loadRemediationPlan(filename, container, button) {
  if (!filename || !container) return;
  button.disabled = true;
  container.hidden = false;
  container.replaceChildren(makeElement("div", "analysis-loading", "Montando plano seguro…"));
  try {
    const data = await api("/api/reports/plan", {
      method: "POST",
      body: JSON.stringify({ filename }),
    });
    renderRemediationPlan(container, data.plan);
    showToast("Plano preparado", "Nenhuma correção foi executada; revise e copie somente o que precisar.");
  } catch (error) {
    container.replaceChildren(makeElement("p", "analysis-error", error.message));
    showToast("Plano não disponível", error.message, true);
  } finally {
    button.disabled = false;
  }
}

function renderReportPreview(report, metadata) {
  const preview = byId("reportPreview");
  preview.replaceChildren();
  const header = makeElement("div", "report-preview-header");
  const heading = makeElement("div");
  heading.append(
    makeElement("span", "panel-label", "Relatório HERMES"),
    makeElement("h2", "", diagnosticLabel(report.type)),
    makeElement("p", "", `${metadata.filename} • ${formatDate(report.completed_at)}`),
  );
  const actions = makeElement("div", "report-preview-actions");
  const analyzeButton = makeElement("button", "button button-secondary");
  analyzeButton.type = "button";
  analyzeButton.append(icon("brain"), document.createTextNode(" Analisar com IA"));
  const planButton = makeElement("button", "button button-ghost");
  planButton.type = "button";
  planButton.append(icon("check"), document.createTextNode(" Plano seguro"));
  const baselineButton = makeElement("button", "button button-ghost");
  baselineButton.type = "button";
  baselineButton.append(
    icon("report"),
    document.createTextNode(metadata.filename === state.baselineFilename ? " Referência fixada" : " Fixar referência"),
  );
  const htmlButton = makeElement("a", "button button-ghost");
  htmlButton.href = reportExportUrl(metadata.filename);
  htmlButton.append(icon("copy"), document.createTextNode(" Exportar HTML"));
  const exportButton = makeElement("button", "button button-ghost");
  exportButton.type = "button";
  exportButton.append(icon("report"), document.createTextNode(" Exportar JSON"));
  exportButton.addEventListener("click", () => downloadJson(metadata.filename, report));
  actions.append(analyzeButton, planButton, baselineButton, htmlButton, exportButton);
  header.append(heading, actions);

  const body = makeElement("div", "report-preview-body");
  body.appendChild(reportStats(report.summary, report.duration_seconds));
  const findings = makeElement("div", "finding-list");
  const reportFindings = report.findings || [];
  if (reportFindings.length) reportFindings.forEach((finding) => findings.appendChild(findingCard(finding)));
  else findings.appendChild(makeElement("p", "muted-value", "Este relatório não possui achados estruturados."));
  body.appendChild(findings);
  const analysis = makeElement("section", "ai-analysis-card");
  analysis.hidden = true;
  analyzeButton.addEventListener("click", () => analyzeReport(metadata.filename, analysis, analyzeButton));
  body.appendChild(analysis);
  const plan = makeElement("section", "remediation-plan");
  plan.hidden = true;
  planButton.addEventListener("click", () => loadRemediationPlan(metadata.filename, plan, planButton));
  baselineButton.addEventListener("click", () => saveBaseline(metadata.filename, baselineButton));
  body.appendChild(plan);
  const raw = makeElement("details", "report-raw");
  raw.append(makeElement("summary", "", "Visualizar dados brutos do relatório"), makeElement("pre", "", JSON.stringify(report, null, 2)));
  body.appendChild(raw);
  preview.append(header, body);
}

async function openReport(filename) {
  if (!filename) return;
  navigate("reports");
  state.activeReport = filename;
  renderReportsList(state.reports);
  const preview = byId("reportPreview");
  preview.replaceChildren(makeElement("div", "empty-state", "Carregando relatório…"));
  try {
    const data = await api(`/api/reports/${encodeURIComponent(filename)}`);
    const metadata = state.reports.find((item) => item.filename === filename) || { filename };
    renderReportPreview(data.report, metadata);
  } catch (error) {
    preview.replaceChildren(makeElement("div", "empty-state", `Não foi possível abrir o relatório: ${error.message}`));
    showToast("Falha ao abrir relatório", error.message, true);
  }
}

function setDiagnosticButtonsDisabled(disabled) {
  all("[data-start-diagnostic]").forEach((button) => {
    button.disabled = disabled;
  });
}

function startTaskTimer() {
  state.taskStartedAt = Date.now();
  window.clearInterval(state.taskTimerId);
  state.taskTimerId = window.setInterval(() => {
    const elapsed = Math.floor((Date.now() - state.taskStartedAt) / 1000);
    const minutes = String(Math.floor(elapsed / 60)).padStart(2, "0");
    const seconds = String(elapsed % 60).padStart(2, "0");
    byId("taskTimer").textContent = `${minutes}:${seconds}`;
  }, 250);
}

function stopTaskTimer() {
  window.clearInterval(state.taskTimerId);
  state.taskTimerId = null;
}

function renderDiagnosticResult(result) {
  const diagnostic = result.diagnostic;
  const resultPanel = byId("diagnosticResult");
  resultPanel.hidden = false;
  byId("resultStats").replaceWith(reportStats(diagnostic.summary, diagnostic.duration_seconds));
  const stats = document.querySelector("#diagnosticResult .result-stats");
  stats.id = "resultStats";
  const list = byId("diagnosticFindings");
  list.replaceChildren();
  (diagnostic.findings || []).forEach((finding) => list.appendChild(findingCard(finding)));
  if (!diagnostic.findings?.length) list.appendChild(makeElement("p", "muted-value", "Nenhum achado retornado."));
  state.generatedFilename = result.report?.filename || null;
  const analysis = byId("diagnosticAiAnalysis");
  analysis.hidden = true;
  analysis.replaceChildren();
  const plan = byId("diagnosticPlan");
  plan.hidden = true;
  plan.replaceChildren();
  const exportLink = byId("exportGeneratedHtml");
  exportLink.href = state.generatedFilename ? reportExportUrl(state.generatedFilename) : "#";
  exportLink.setAttribute("download", "");
}

async function runDiagnostic(type) {
  if (state.diagnosticRunning) return;
  navigate("diagnostics");
  state.diagnosticRunning = true;
  state.coreBusy = true;
  setDiagnosticButtonsDisabled(true);
  byId("diagnosticResult").hidden = true;
  byId("taskPanel").hidden = false;
  byId("taskTitle").textContent = `Diagnóstico: ${diagnosticLabel(type)}`;
  byId("taskMessage").textContent = "Executando apenas verificações locais permitidas…";
  byId("taskTimer").textContent = "00:00";
  setCoreState("working", "Coletando diagnóstico", diagnosticLabel(type));
  startTaskTimer();

  try {
    const result = await api("/api/diagnostics", {
      method: "POST",
      body: JSON.stringify({ type }),
    });
    renderDiagnosticResult(result);
    showToast("Diagnóstico concluído", `Relatório ${result.report.filename} salvo localmente.`);
    await Promise.all([refreshReports(), refreshSystem()]);
    setCoreState("ready", "Diagnóstico concluído", `${result.diagnostic.summary.alerts || 0} alertas encontrados`);
  } catch (error) {
    setCoreState("error", "Falha no diagnóstico", error.message);
    showToast("Diagnóstico não concluído", error.message, true);
  } finally {
    stopTaskTimer();
    byId("taskPanel").hidden = true;
    state.diagnosticRunning = false;
    state.coreBusy = false;
    setDiagnosticButtonsDisabled(false);
  }
}

function addWelcomeMessage() {
  const message = makeElement("div", "message assistant");
  message.id = "chatWelcome";
  const avatar = makeElement("div", "message-avatar", "H");
  const body = makeElement("div", "message-body");
  body.append(
    makeElement("strong", "", "HERMES"),
    makeElement("p", "", "Pronto para auxiliar no diagnóstico defensivo. Como posso ajudar?"),
  );
  message.append(avatar, body);
  byId("chatOutput").appendChild(message);
}

function addChatMessage(role, text, metadata = {}) {
  const message = makeElement("div", `message ${role}`);
  const avatar = makeElement("div", "message-avatar", role === "user" ? "V" : "H");
  const body = makeElement("div", "message-body");
  const head = makeElement("div", "message-head");
  head.appendChild(makeElement("strong", "", role === "user" ? "Você" : role === "error" ? "Erro" : "HERMES"));
  const metaParts = [];
  if (metadata.mode) metaParts.push(metadata.mode === "deep" ? "Profunda" : "Rápida");
  if (metadata.createdAt) metaParts.push(formatTime(metadata.createdAt));
  if (metaParts.length) head.appendChild(makeElement("small", "", metaParts.join(" • ")));
  if (role === "assistant") {
    const copy = makeElement("button", "message-copy");
    copy.type = "button";
    copy.title = "Copiar resposta";
    copy.setAttribute("aria-label", "Copiar resposta");
    copy.appendChild(icon("copy"));
    copy.addEventListener("click", () => copyText(text));
    head.appendChild(copy);
  }
  body.append(head, makeElement("p", "", text));
  message.append(avatar, body);
  byId("chatOutput").appendChild(message);
  if (metadata.scroll !== false) byId("chatOutput").scrollTop = byId("chatOutput").scrollHeight;
  return message;
}

function renderChatHistory(messages) {
  const output = byId("chatOutput");
  output.replaceChildren();
  if (!messages?.length) {
    addWelcomeMessage();
    return;
  }
  messages.forEach((message) => {
    addChatMessage(message.role, message.content, {
      mode: message.mode,
      createdAt: message.created_at,
      scroll: false,
    });
  });
  output.scrollTop = output.scrollHeight;
}

async function refreshChatHistory() {
  try {
    const data = await api("/api/chat/history");
    renderChatHistory(data.messages || []);
    state.chatHistoryLoaded = true;
  } catch (error) {
    if (!state.chatHistoryLoaded) showToast("Histórico indisponível", error.message, true);
  }
}

async function clearChatHistoryUi() {
  if (!window.confirm("Limpar todo o histórico local de conversas?")) return;
  try {
    await api("/api/chat/history", { method: "DELETE" });
    renderChatHistory([]);
    showToast("Histórico limpo", "As conversas locais foram removidas.");
  } catch (error) {
    showToast("Não foi possível limpar", error.message, true);
  }
}

function addTypingMessage() {
  const message = makeElement("div", "message assistant");
  const avatar = makeElement("div", "message-avatar", "H");
  const body = makeElement("div", "message-body");
  body.appendChild(makeElement("strong", "", "HERMES"));
  const dots = makeElement("div", "typing-dots");
  dots.append(makeElement("span"), makeElement("span"), makeElement("span"));
  body.appendChild(dots);
  message.append(avatar, body);
  byId("chatOutput").appendChild(message);
  byId("chatOutput").scrollTop = byId("chatOutput").scrollHeight;
  return message;
}

async function sendChatMessage(text) {
  const cleanText = text.trim();
  if (!cleanText) return;
  addChatMessage("user", cleanText, { mode: state.responseMode, createdAt: new Date().toISOString() });
  const pending = addTypingMessage();
  const submit = byId("chatForm").querySelector("button[type='submit']");
  submit.disabled = true;
  state.coreBusy = true;
  const deepMode = state.responseMode === "deep";
  setCoreState("working", deepMode ? "Executando análise profunda" : "Analisando solicitação", "Assistente IA");
  try {
    const data = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message: cleanText, mode: state.responseMode }),
    });
    pending.remove();
    const savedAssistant = data.messages?.find((message) => message.role === "assistant");
    addChatMessage("assistant", data.answer || "A IA não retornou conteúdo.", {
      mode: data.mode,
      createdAt: savedAssistant?.created_at || data.timestamp,
    });
    setCoreState("ready", "Sistema pronto", "Resposta concluída");
  } catch (error) {
    pending.remove();
    addChatMessage("error", error.message);
    setCoreState("error", "Falha no assistente", error.message);
  } finally {
    submit.disabled = false;
    state.coreBusy = false;
  }
}

function knowledgeCollectionName(collectionId) {
  if (!collectionId) return "Toda a base";
  return state.knowledgeCollections.find((collection) => collection.id === collectionId)?.name || "Geral";
}

function knowledgeImportCollectionId() {
  return state.knowledgeCollectionId || "general";
}

function updateKnowledgeReportOptions() {
  const select = byId("knowledgeReportSelect");
  if (!select) return;
  const previous = select.value;
  select.replaceChildren();
  const placeholder = makeElement("option", "", "Selecione um relatório");
  placeholder.value = "";
  select.appendChild(placeholder);
  state.reports.forEach((report) => {
    const option = makeElement(
      "option",
      "",
      `${diagnosticLabel(report.type)} — ${formatDate(report.completed_at)}`,
    );
    option.value = report.filename;
    option.title = report.filename;
    select.appendChild(option);
  });
  if (state.reports.some((report) => report.filename === previous)) select.value = previous;
  byId("importKnowledgeReport").disabled = !select.value;
}

function renderKnowledgeStats() {
  const summary = state.knowledgeSummary || {};
  byId("knowledgeDocumentsStat").textContent = summary.documents ?? 0;
  byId("knowledgeCollectionsStat").textContent = summary.collections ?? 0;
  byId("knowledgeChunksStat").textContent = summary.chunks ?? 0;
  byId("knowledgeStorageStat").textContent = formatBytes(summary.size_bytes || 0);
  byId("knowledgeEngine").textContent = summary.index_engine || "SQLite local";
  byId("knowledgeCount").textContent = summary.documents ?? 0;
  const capacity = Number(summary.capacity_bytes || 1);
  byId("knowledgeCapacityBar").style.width = `${clamp((Number(summary.size_bytes || 0) / capacity) * 100, 0, 100)}%`;
}

function updateKnowledgeScope() {
  const selectedCount = state.selectedKnowledgeDocuments.size;
  const selectionLabel = `${selectedCount} ${selectedCount === 1 ? "selecionado" : "selecionados"}`;
  byId("knowledgeSelectionCount").textContent = selectionLabel;
  byId("clearKnowledgeSelection").disabled = selectedCount === 0;
  if (selectedCount) {
    byId("knowledgeScopeLabel").textContent = selectionLabel;
    byId("knowledgeQueryHint").textContent = "A consulta usará somente os documentos marcados abaixo.";
  } else if (state.knowledgeCollectionId) {
    byId("knowledgeScopeLabel").textContent = knowledgeCollectionName(state.knowledgeCollectionId);
    byId("knowledgeQueryHint").textContent = "Sem arquivos selecionados, a pesquisa usa a coleção ativa.";
  } else {
    byId("knowledgeScopeLabel").textContent = "Toda a base";
    byId("knowledgeQueryHint").textContent = "Sem arquivos selecionados, a pesquisa usa toda a base local.";
  }
  byId("knowledgeImportTarget").textContent = knowledgeCollectionName(knowledgeImportCollectionId());
}

function renderKnowledgeCollections() {
  const list = byId("knowledgeCollectionsList");
  list.replaceChildren();
  byId("allKnowledgeCount").textContent = state.knowledgeSummary?.documents ?? 0;
  byId("allKnowledgeCollection").classList.toggle("is-active", !state.knowledgeCollectionId);

  state.knowledgeCollections.forEach((collection) => {
    const row = makeElement("div", "knowledge-collection-row");
    row.classList.toggle("is-active", collection.id === state.knowledgeCollectionId);
    const select = makeElement("button", "knowledge-collection");
    select.type = "button";
    select.dataset.knowledgeCollection = collection.id;
    const label = makeElement("span");
    label.append(icon("folder"), document.createTextNode(collection.name));
    select.append(label, makeElement("strong", "", collection.document_count || 0));
    select.addEventListener("click", () => selectKnowledgeCollection(collection.id));
    row.appendChild(select);
    if (!collection.protected) {
      const remove = makeElement("button", "knowledge-collection-delete");
      remove.type = "button";
      remove.title = `Excluir coleção ${collection.name}`;
      remove.setAttribute("aria-label", `Excluir coleção ${collection.name}`);
      remove.appendChild(icon("close"));
      remove.addEventListener("click", () => deleteKnowledgeCollection(collection));
      row.appendChild(remove);
    }
    list.appendChild(row);
  });
}

function visibleKnowledgeDocuments() {
  if (!state.knowledgeCollectionId) return state.knowledgeDocuments;
  return state.knowledgeDocuments.filter(
    (document) => document.collection_id === state.knowledgeCollectionId,
  );
}

function knowledgeSourceLabel(sourceType) {
  return sourceType === "report" ? "Relatório HERMES" : "Documento";
}

function renderKnowledgeDocuments() {
  const list = byId("knowledgeDocumentsList");
  list.replaceChildren();
  const documents = visibleKnowledgeDocuments();
  if (!documents.length) {
    const empty = makeElement("div", "empty-state");
    const emptyIcon = makeElement("span", "empty-icon");
    emptyIcon.appendChild(icon("knowledge"));
    empty.append(
      emptyIcon,
      makeElement("strong", "", "Nenhuma fonte nesta coleção"),
      makeElement("p", "", "Importe arquivos ou adicione um relatório HERMES."),
    );
    list.appendChild(empty);
    updateKnowledgeScope();
    return;
  }

  documents.forEach((documentData) => {
    const card = makeElement("article", "knowledge-document-card");
    card.classList.toggle("is-selected", state.selectedKnowledgeDocuments.has(documentData.id));
    const checkboxLabel = makeElement("label", "knowledge-document-check");
    const checkbox = makeElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = state.selectedKnowledgeDocuments.has(documentData.id);
    checkbox.setAttribute("aria-label", `Selecionar ${documentData.title}`);
    const customCheck = makeElement("span");
    checkboxLabel.append(checkbox, customCheck);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) state.selectedKnowledgeDocuments.add(documentData.id);
      else state.selectedKnowledgeDocuments.delete(documentData.id);
      card.classList.toggle("is-selected", checkbox.checked);
      updateKnowledgeScope();
    });

    const fileIcon = makeElement("span", "knowledge-document-icon");
    fileIcon.appendChild(icon(documentData.source_type === "report" ? "report" : "knowledge"));
    const copy = makeElement("div", "knowledge-document-copy");
    const title = makeElement("strong", "", documentData.title);
    title.title = documentData.filename;
    const meta = makeElement(
      "span",
      "",
      `${documentData.collection_name} • ${formatBytes(documentData.size_bytes)} • ${documentData.chunk_count} trechos`,
    );
    const badges = makeElement("div", "knowledge-document-badges");
    badges.append(
      makeElement("span", "source-type-badge", knowledgeSourceLabel(documentData.source_type)),
      makeElement("span", "extension-badge", documentData.extension.replace(".", "").toUpperCase()),
    );
    copy.append(title, meta, badges);

    const actions = makeElement("div", "knowledge-document-actions");
    const preview = makeElement("button", "icon-button");
    preview.type = "button";
    preview.title = "Visualizar fonte";
    preview.setAttribute("aria-label", `Visualizar ${documentData.title}`);
    preview.appendChild(icon("search"));
    preview.addEventListener("click", () => openKnowledgeDocument(documentData.id));
    const remove = makeElement("button", "icon-button danger-icon");
    remove.type = "button";
    remove.title = "Excluir fonte";
    remove.setAttribute("aria-label", `Excluir ${documentData.title}`);
    remove.appendChild(icon("close"));
    remove.addEventListener("click", () => deleteKnowledgeDocument(documentData));
    actions.append(preview, remove);

    card.append(checkboxLabel, fileIcon, copy, actions);
    list.appendChild(card);
  });
  updateKnowledgeScope();
}

function selectKnowledgeCollection(collectionId) {
  state.knowledgeCollectionId = collectionId || "";
  state.selectedKnowledgeDocuments.clear();
  byId("knowledgeResults").hidden = true;
  renderKnowledgeCollections();
  renderKnowledgeDocuments();
}

async function refreshKnowledge() {
  try {
    const data = await api("/api/knowledge");
    state.knowledgeSummary = data.summary || {};
    state.knowledgeCollections = data.collections || [];
    state.knowledgeDocuments = data.documents || [];
    const validIds = new Set(state.knowledgeDocuments.map((document) => document.id));
    [...state.selectedKnowledgeDocuments].forEach((id) => {
      if (!validIds.has(id)) state.selectedKnowledgeDocuments.delete(id);
    });
    if (
      state.knowledgeCollectionId
      && !state.knowledgeCollections.some((collection) => collection.id === state.knowledgeCollectionId)
    ) {
      state.knowledgeCollectionId = "";
    }
    renderKnowledgeStats();
    renderKnowledgeCollections();
    renderKnowledgeDocuments();
    updateKnowledgeReportOptions();
    return data;
  } catch (error) {
    showToast("Base local indisponível", error.message, true);
    return null;
  }
}

function knowledgeQueryScope() {
  const selected = [...state.selectedKnowledgeDocuments];
  return {
    document_ids: selected,
    collection_ids: selected.length || !state.knowledgeCollectionId
      ? []
      : [state.knowledgeCollectionId],
  };
}

function knowledgeSourceCard(source, number = source.source_number) {
  const card = makeElement("article", "knowledge-source-card");
  const header = makeElement("div", "knowledge-source-head");
  const sourceNumber = makeElement("span", "knowledge-source-number", `Fonte ${number}`);
  const heading = makeElement("div");
  heading.append(
    makeElement("strong", "", source.title || source.filename),
    makeElement("small", "", `${source.collection_name} • trecho ${Number(source.chunk_index || 0) + 1}`),
  );
  const open = makeElement("button", "button button-ghost button-compact");
  open.type = "button";
  open.append(icon("search"), document.createTextNode(" Abrir"));
  open.addEventListener("click", () => openKnowledgeDocument(source.document_id));
  header.append(sourceNumber, heading, open);
  card.append(header, makeElement("p", "", source.snippet || "Trecho local disponível."));
  return card;
}

function renderKnowledgeSearch(search) {
  const container = byId("knowledgeResults");
  container.hidden = false;
  container.replaceChildren();
  const header = makeElement("div", "knowledge-results-heading");
  header.append(
    makeElement("div", "", "Resultados locais"),
    makeElement("span", "", `${search.result_count || 0} encontrados`),
  );
  container.appendChild(header);
  if (!search.results?.length) {
    container.appendChild(makeElement("p", "knowledge-no-results", "Nenhum trecho relevante foi encontrado. Tente termos mais específicos."));
    return;
  }
  const results = makeElement("div", "knowledge-source-list");
  search.results.forEach((source) => results.appendChild(knowledgeSourceCard(source)));
  container.appendChild(results);
}

function renderKnowledgeAnswer(data) {
  const container = byId("knowledgeResults");
  container.hidden = false;
  container.replaceChildren();
  const answer = makeElement("article", "knowledge-answer");
  const header = makeElement("div", "knowledge-answer-head");
  const title = makeElement("div");
  title.append(
    makeElement("span", "panel-label", "Resposta fundamentada"),
    makeElement("h3", "", "HERMES • Base Local"),
  );
  const copy = makeElement("button", "button button-ghost button-compact");
  copy.type = "button";
  copy.append(icon("copy"), document.createTextNode(" Copiar"));
  copy.addEventListener("click", () => copyText(data.answer));
  header.append(title, copy);
  answer.append(
    header,
    makeElement("p", "knowledge-answer-text", data.answer),
    makeElement("small", "knowledge-answer-meta", `${data.sources?.length || 0} fontes locais • ${formatDuration(data.duration_seconds)}`),
  );
  container.appendChild(answer);
  const sourcesHeading = makeElement("div", "knowledge-results-heading");
  sourcesHeading.append(makeElement("div", "", "Fontes consultadas"), makeElement("span", "", data.sources?.length || 0));
  container.appendChild(sourcesHeading);
  const sources = makeElement("div", "knowledge-source-list");
  (data.sources || []).forEach((source) => sources.appendChild(knowledgeSourceCard(source)));
  container.appendChild(sources);
}

async function runKnowledgeQuery(useAI) {
  const query = byId("knowledgeQuery").value.trim();
  if (!query) {
    showToast("Informe uma pergunta", "Digite um termo ou uma pergunta para consultar a base.", true);
    byId("knowledgeQuery").focus();
    return;
  }
  const searchButton = byId("searchKnowledge");
  const askButton = byId("askKnowledge");
  searchButton.disabled = true;
  askButton.disabled = true;
  const container = byId("knowledgeResults");
  container.hidden = false;
  container.replaceChildren(makeElement("div", "analysis-loading", useAI ? "Consultando fontes e preparando resposta local…" : "Pesquisando o índice local…"));
  state.knowledgeBusy = true;
  state.coreBusy = true;
  setCoreState("working", useAI ? "Consultando base local" : "Pesquisando documentos", "Conhecimento privado");
  try {
    const scope = knowledgeQueryScope();
    const data = await api(useAI ? "/api/knowledge/ask" : "/api/knowledge/search", {
      method: "POST",
      body: JSON.stringify({
        [useAI ? "question" : "query"]: query,
        ...scope,
        mode: state.responseMode,
        limit: 10,
      }),
    });
    if (useAI) renderKnowledgeAnswer(data);
    else renderKnowledgeSearch(data.search);
    setCoreState("ready", useAI ? "Resposta fundamentada" : "Busca concluída", useAI ? `${data.sources?.length || 0} fontes consultadas` : `${data.search?.result_count || 0} trechos encontrados`);
  } catch (error) {
    container.replaceChildren(makeElement("p", "analysis-error", error.message));
    showToast(useAI ? "Resposta não concluída" : "Busca não concluída", error.message, true);
    setCoreState("error", "Falha na base local", error.message);
  } finally {
    state.knowledgeBusy = false;
    state.coreBusy = false;
    searchButton.disabled = false;
    askButton.disabled = false;
  }
}

async function importKnowledgeFiles(fileList) {
  const files = Array.from(fileList || []).slice(0, 20);
  if (!files.length) return;
  const allowed = new Set(["txt", "md", "json", "log"]);
  const status = byId("knowledgeUploadStatus");
  status.hidden = false;
  const collectionId = knowledgeImportCollectionId();
  let imported = 0;
  let duplicates = 0;
  const failures = [];
  for (let index = 0; index < files.length; index += 1) {
    const file = files[index];
    const extension = file.name.includes(".") ? file.name.split(".").pop().toLowerCase() : "";
    status.textContent = `Importando ${index + 1} de ${files.length}: ${file.name}`;
    if (!allowed.has(extension)) {
      failures.push(`${file.name}: formato não permitido`);
      continue;
    }
    if (file.size > 2 * 1024 * 1024) {
      failures.push(`${file.name}: excede 2 MB`);
      continue;
    }
    try {
      const content = await file.text();
      const data = await api("/api/knowledge/documents", {
        method: "POST",
        body: JSON.stringify({ filename: file.name, content, collection_id: collectionId }),
      });
      if (data.document?.duplicate) duplicates += 1;
      else imported += 1;
    } catch (error) {
      failures.push(`${file.name}: ${error.message}`);
    }
  }
  byId("knowledgeFileInput").value = "";
  status.textContent = `${imported} importados${duplicates ? ` • ${duplicates} já existentes` : ""}${failures.length ? ` • ${failures.length} falharam` : ""}`;
  await refreshKnowledge();
  if (failures.length) showToast("Importação parcial", failures.slice(0, 3).join(" | "), true);
  else showToast("Fontes atualizadas", `${imported} documentos adicionados${duplicates ? ` e ${duplicates} duplicados ignorados` : ""}.`);
}

async function importKnowledgeReport() {
  const filename = byId("knowledgeReportSelect").value;
  if (!filename) return;
  const button = byId("importKnowledgeReport");
  button.disabled = true;
  try {
    const data = await api("/api/knowledge/reports", {
      method: "POST",
      body: JSON.stringify({ filename, collection_id: knowledgeImportCollectionId() }),
    });
    await refreshKnowledge();
    showToast(
      data.document?.duplicate ? "Relatório já existente" : "Relatório adicionado",
      data.document?.duplicate ? "Essa coleta já estava indexada na coleção." : "A coleta agora pode ser pesquisada como fonte local.",
    );
  } catch (error) {
    showToast("Relatório não adicionado", error.message, true);
  } finally {
    button.disabled = !byId("knowledgeReportSelect").value;
  }
}

async function createKnowledgeCollection(event) {
  event.preventDefault();
  const input = byId("knowledgeCollectionName");
  const name = input.value.trim();
  if (!name) return;
  try {
    const data = await api("/api/knowledge/collections", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
    input.value = "";
    await refreshKnowledge();
    selectKnowledgeCollection(data.collection.id);
    showToast("Coleção criada", `${data.collection.name} está pronta para receber fontes.`);
  } catch (error) {
    showToast("Coleção não criada", error.message, true);
  }
}

async function deleteKnowledgeDocument(documentData) {
  if (!window.confirm(`Excluir a fonte “${documentData.title}” da base local?`)) return;
  try {
    await api(`/api/knowledge/documents/${encodeURIComponent(documentData.id)}`, { method: "DELETE" });
    state.selectedKnowledgeDocuments.delete(documentData.id);
    await refreshKnowledge();
    showToast("Fonte excluída", "O documento e seus trechos foram removidos da base local.");
  } catch (error) {
    showToast("Não foi possível excluir", error.message, true);
  }
}

async function deleteKnowledgeCollection(collection) {
  const message = `Excluir a coleção “${collection.name}” e seus ${collection.document_count || 0} documentos?`;
  if (!window.confirm(message)) return;
  try {
    await api(`/api/knowledge/collections/${encodeURIComponent(collection.id)}`, { method: "DELETE" });
    state.knowledgeCollectionId = "";
    state.selectedKnowledgeDocuments.clear();
    await refreshKnowledge();
    showToast("Coleção excluída", "A coleção e suas fontes locais foram removidas.");
  } catch (error) {
    showToast("Não foi possível excluir", error.message, true);
  }
}

async function clearKnowledgeBase() {
  if (!window.confirm("Limpar todos os documentos e coleções personalizadas da Base Local?")) return;
  try {
    const data = await api("/api/knowledge", { method: "DELETE" });
    state.knowledgeCollectionId = "";
    state.selectedKnowledgeDocuments.clear();
    byId("knowledgeResults").hidden = true;
    await refreshKnowledge();
    showToast("Base local limpa", `${data.deleted_documents || 0} documentos foram removidos.`);
  } catch (error) {
    showToast("Não foi possível limpar", error.message, true);
  }
}

async function openKnowledgeDocument(documentId) {
  try {
    const data = await api(`/api/knowledge/documents/${encodeURIComponent(documentId)}`);
    const documentData = data.document;
    byId("knowledgePreviewCollection").textContent = `${documentData.collection_name} • ${knowledgeSourceLabel(documentData.source_type)}`;
    byId("knowledgePreviewTitle").textContent = documentData.title;
    byId("knowledgePreviewMeta").textContent = `${documentData.filename} • ${formatBytes(documentData.size_bytes)} • ${documentData.chunk_count} trechos`;
    byId("knowledgePreviewContent").textContent = documentData.content || "Sem conteúdo para visualizar.";
    byId("knowledgePreviewNote").hidden = !documentData.content_truncated;
    const dialog = byId("knowledgePreviewDialog");
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  } catch (error) {
    showToast("Fonte indisponível", error.message, true);
  }
}

function closeKnowledgePreview() {
  const dialog = byId("knowledgePreviewDialog");
  if (typeof dialog.close === "function") dialog.close();
  else dialog.removeAttribute("open");
}

function bindEvents() {
  all(".nav-item[data-view]").forEach((button) => {
    button.addEventListener("click", () => navigate(button.dataset.view));
  });
  all("[data-navigate]").forEach((button) => {
    button.addEventListener("click", () => navigate(button.dataset.navigate));
  });
  all("[data-start-diagnostic]").forEach((button) => {
    button.addEventListener("click", () => runDiagnostic(button.dataset.startDiagnostic));
  });
  all("[data-prompt]").forEach((button) => {
    button.addEventListener("click", () => {
      navigate("assistant");
      byId("message").value = button.dataset.prompt;
      byId("message").focus();
    });
  });
  all("[data-response-mode]").forEach((button) => {
    button.addEventListener("click", () => setResponseMode(button.dataset.responseMode));
  });
  all("[data-download-profile]").forEach((button) => {
    button.addEventListener("click", () => requestModelDownload(button.dataset.downloadProfile));
  });

  byId("menuToggle").addEventListener("click", () => {
    const open = document.body.classList.toggle("sidebar-open");
    byId("menuToggle").setAttribute("aria-expanded", String(open));
  });
  byId("sidebarBackdrop").addEventListener("click", closeSidebar);
  byId("enableNotifications").addEventListener("click", toggleNotifications);
  byId("refreshMonitor").addEventListener("click", async () => {
    const data = await refreshMonitor(false);
    if (data) showToast("Monitor atualizado", "Métricas e alertas locais foram consultados.");
  });
  byId("startMonitor").addEventListener("click", startMonitor);
  byId("stopMonitor").addEventListener("click", stopMonitor);
  byId("monitorConfigForm").addEventListener("submit", saveMonitorConfiguration);
  byId("monitorConfigForm").addEventListener("input", () => {
    state.monitorConfigDirty = true;
  });
  byId("acknowledgeAllAlerts").addEventListener("click", () => acknowledgeMonitorAlerts());
  byId("clearMonitorHistory").addEventListener("click", clearMonitorHistory);
  byId("exportMonitorData").addEventListener("click", exportMonitorData);
  byId("refreshIncidents").addEventListener("click", async () => {
    const data = await refreshIncidents(false);
    if (data) showToast("Incidentes atualizados", "A fila e os indicadores foram consultados.");
  });
  byId("incidentStatusFilter").addEventListener("change", () => refreshIncidents(false));
  byId("newIncident").addEventListener("click", showIncidentDialog);
  byId("incidentCreateForm").addEventListener("submit", createManualIncident);
  byId("closeIncidentDialog").addEventListener("click", closeIncidentDialog);
  byId("cancelIncident").addEventListener("click", closeIncidentDialog);
  byId("incidentCreateDialog").addEventListener("click", (event) => {
    if (event.target === byId("incidentCreateDialog")) closeIncidentDialog();
  });
  byId("openKnowledgeFiles").addEventListener("click", () => byId("knowledgeFileInput").click());
  byId("knowledgeDropzone").addEventListener("click", () => byId("knowledgeFileInput").click());
  byId("knowledgeFileInput").addEventListener("change", (event) => importKnowledgeFiles(event.target.files));
  ["dragenter", "dragover"].forEach((eventName) => {
    byId("knowledgeDropzone").addEventListener(eventName, (event) => {
      event.preventDefault();
      byId("knowledgeDropzone").classList.add("is-dragging");
    });
  });
  ["dragleave", "drop"].forEach((eventName) => {
    byId("knowledgeDropzone").addEventListener(eventName, (event) => {
      event.preventDefault();
      byId("knowledgeDropzone").classList.remove("is-dragging");
      if (eventName === "drop") importKnowledgeFiles(event.dataTransfer.files);
    });
  });
  byId("refreshKnowledge").addEventListener("click", refreshKnowledge);
  byId("allKnowledgeCollection").addEventListener("click", () => selectKnowledgeCollection(""));
  byId("knowledgeCollectionForm").addEventListener("submit", createKnowledgeCollection);
  byId("clearKnowledge").addEventListener("click", clearKnowledgeBase);
  byId("clearKnowledgeSelection").addEventListener("click", () => {
    state.selectedKnowledgeDocuments.clear();
    renderKnowledgeDocuments();
  });
  byId("knowledgeReportSelect").addEventListener("change", (event) => {
    byId("importKnowledgeReport").disabled = !event.target.value;
  });
  byId("importKnowledgeReport").addEventListener("click", importKnowledgeReport);
  byId("searchKnowledge").addEventListener("click", () => runKnowledgeQuery(false));
  byId("knowledgeQueryForm").addEventListener("submit", (event) => {
    event.preventDefault();
    runKnowledgeQuery(true);
  });
  byId("knowledgeQuery").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && event.ctrlKey) {
      event.preventDefault();
      byId("knowledgeQueryForm").requestSubmit();
    }
  });
  byId("closeKnowledgePreview").addEventListener("click", closeKnowledgePreview);
  byId("knowledgePreviewDialog").addEventListener("click", (event) => {
    if (event.target === byId("knowledgePreviewDialog")) closeKnowledgePreview();
  });
  byId("refreshReports").addEventListener("click", refreshReports);
  byId("baselineReportSelect").addEventListener("change", () => {
    state.lastComparison = null;
    byId("comparisonResult").hidden = true;
    updateComparisonAvailability();
  });
  byId("currentReportSelect").addEventListener("change", () => {
    state.lastComparison = null;
    byId("comparisonResult").hidden = true;
    updateComparisonAvailability();
  });
  byId("saveBaselineReport").addEventListener("click", () => saveBaseline(byId("baselineReportSelect").value));
  byId("runReportComparison").addEventListener("click", () => runReportComparison(false));
  byId("analyzeReportComparison").addEventListener("click", () => runReportComparison(true));
  byId("refreshDiagnostics").addEventListener("click", async () => {
    await Promise.all([refreshSystem(), refreshHealth()]);
    showToast("Dados atualizados", "Estado local consultado com sucesso.");
  });
  byId("openLatestReport").addEventListener("click", () => openReport(state.latestFilename));
  byId("viewGeneratedReport").addEventListener("click", () => openReport(state.generatedFilename));
  byId("analyzeGeneratedReport").addEventListener("click", () => analyzeReport(
    state.generatedFilename,
    byId("diagnosticAiAnalysis"),
    byId("analyzeGeneratedReport"),
  ));
  byId("planGeneratedReport").addEventListener("click", () => loadRemediationPlan(
    state.generatedFilename,
    byId("diagnosticPlan"),
    byId("planGeneratedReport"),
  ));
  byId("settingsForm").addEventListener("submit", saveConfiguration);
  byId("cancelModelDownload").addEventListener("click", pauseModelDownload);
  byId("runBenchmark").addEventListener("click", runBenchmark);
  byId("exportBackup").addEventListener("click", exportBackup);
  byId("importBackup").addEventListener("click", () => byId("backupFileInput").click());
  byId("backupFileInput").addEventListener("change", (event) => restoreBackup(event.target.files?.[0]));
  byId("clearChatHistory").addEventListener("click", clearChatHistoryUi);

  byId("chatForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = byId("message");
    const text = input.value;
    if (!text.trim()) return;
    input.value = "";
    await sendChatMessage(text);
  });
  byId("message").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && event.ctrlKey) {
      event.preventDefault();
      byId("chatForm").requestSubmit();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeSidebar();
  });
  window.addEventListener("resize", () => {
    if (state.monitorData && !byId("view-monitor").hidden) {
      drawMonitorChart(state.monitorData.samples || []);
    }
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && state.monitorData?.runtime?.running) refreshMonitor(true);
  });
}

async function initialise() {
  loadNotificationPreference();
  bindEvents();
  updateClock();
  window.setInterval(updateClock, 1000);
  const results = await Promise.allSettled([
    refreshHealth(),
    refreshSystem(),
    refreshReports(),
    refreshConfiguration(),
    refreshChatHistory(),
    refreshModels(false),
    refreshBenchmark(),
    refreshKnowledge(),
    refreshMonitor(true),
    refreshIncidents(true),
  ]);
  const failed = results.filter((result) => result.status === "rejected");
  if (failed.length) showToast("Inicialização parcial", "Alguns dados ainda não estão disponíveis.", true);

  window.setInterval(() => {
    if (!document.hidden) refreshHealth().catch(() => {});
  }, 15000);
  window.setInterval(() => {
    if (!document.hidden && !state.diagnosticRunning) refreshSystem();
  }, 10000);
  window.setInterval(() => {
    if (!document.hidden && !state.diagnosticRunning) refreshReports();
  }, 45000);
  window.setInterval(() => {
    if (!document.hidden && !state.modelPollId) refreshModels(false);
  }, 30000);
}

initialise();
