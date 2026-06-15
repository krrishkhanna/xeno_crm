const state = {
  campaignId: null,
};

const crmBaseUrlInput = document.getElementById("crmBaseUrl");
const channelBaseUrlInput = document.getElementById("channelBaseUrl");
const resultBox = document.getElementById("resultBox");
const commTable = document.getElementById("commTable");
const analyticsBox = document.getElementById("analyticsBox");
const crmStatus = document.getElementById("crmStatus");
const channelStatus = document.getElementById("channelStatus");

const templates = {
  winback: "Send a win-back campaign to dormant customers who have not ordered in 30 days",
  loyalty: "Create a loyalty campaign for high-value customers",
  welcome: "Send a welcome campaign to new customers",
};

function crmUrl(path) {
  return `${crmBaseUrlInput.value.replace(/\/$/, "")}${path}`;
}

function channelUrl(path) {
  return `${channelBaseUrlInput.value.replace(/\/$/, "")}${path}`;
}

async function checkHealth() {
  try {
    const crm = await fetch(crmUrl("/health")).then((response) => response.json());
    crmStatus.textContent = `CRM: ${crm.status}`;
    crmStatus.style.borderColor = "rgba(120, 240, 184, 0.5)";
  } catch {
    crmStatus.textContent = "CRM: offline";
    crmStatus.style.borderColor = "rgba(255, 127, 142, 0.5)";
  }

  try {
    const channel = await fetch(channelUrl("/health")).then((response) => response.json());
    channelStatus.textContent = `Channel: ${channel.status}`;
    channelStatus.style.borderColor = "rgba(120, 240, 184, 0.5)";
  } catch {
    channelStatus.textContent = "Channel: offline";
    channelStatus.style.borderColor = "rgba(255, 127, 142, 0.5)";
  }
}

async function runCampaign(message) {
  resultBox.textContent = "Running campaign...";
  const response = await fetch(crmUrl("/api/v1/agent/chat"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, provider: "local", stream: false }),
  });
  const data = await response.json();
  state.campaignId = data.campaign_id;
  resultBox.textContent = JSON.stringify(data, null, 2);
  await loadAnalytics();
  await loadCommunications();
}

async function loadAnalytics() {
  if (!state.campaignId) return;
  const response = await fetch(crmUrl(`/api/v1/campaigns/${state.campaignId}/analytics`));
  const data = await response.json();
  analyticsBox.innerHTML = `
    <div><strong>sent</strong><span>${data.sent}</span></div>
    <div><strong>delivered</strong><span>${data.delivered}</span></div>
    <div><strong>failed</strong><span>${data.failed}</span></div>
    <div><strong>open rate</strong><span>${data.open_rate}%</span></div>
  `;
}

async function loadCommunications() {
  const response = await fetch(crmUrl("/api/v1/communications?limit=20"));
  const rows = await response.json();
  commTable.innerHTML = rows
    .map(
      (row) => `
      <tr>
        <td>${row.campaign_id}</td>
        <td>${row.customer_id}</td>
        <td>${row.status}</td>
        <td>${row.channel}</td>
        <td>${row.failure_reason ?? ""}</td>
      </tr>`
    )
    .join("");
}

document.querySelectorAll("[data-template]").forEach((button) => {
  button.addEventListener("click", () => runCampaign(templates[button.dataset.template]));
});

document.getElementById("refreshBtn").addEventListener("click", checkHealth);
document.getElementById("loadLatest").addEventListener("click", loadAnalytics);
document.getElementById("loadCommunications").addEventListener("click", loadCommunications);
document.getElementById("clearResult").addEventListener("click", () => {
  resultBox.textContent = "Run a campaign to see the JSON response here.";
});

checkHealth();
