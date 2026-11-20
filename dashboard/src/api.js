const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const API_KEY = import.meta.env.VITE_API_KEY || "";

export const GUILD_ID = import.meta.env.VITE_DISCORD_GUILD_ID || "";

async function request(path) {
  const response = await fetch(`${API_URL}${path}`, {
    headers: API_KEY ? { "X-API-Key": API_KEY } : {},
  });

  if (response.status === 401) {
    throw new Error("A API pediu autenticação. Preencha VITE_API_KEY no .env do dashboard.");
  }
  if (!response.ok) {
    throw new Error(`A API respondeu ${response.status}. O bot e a API estão rodando?`);
  }
  return response.json();
}

export function loadDashboard(guildId, { days = 14, limit = 8 } = {}) {
  return Promise.all([
    request(`/api/guilds/${guildId}/metrics`),
    request(`/api/guilds/${guildId}/activity?limit=${limit}&days=${days}`),
    request(`/api/guilds/${guildId}/timeline?days=${days}`),
  ]).then(([metrics, activity, timeline]) => ({
    metrics,
    channels: activity.channels,
    timeline: timeline.timeline,
  }));
}
