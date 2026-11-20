import { useCallback, useEffect, useState } from "react";
import ActivityChart from "./components/ActivityChart";
import { GUILD_ID, loadDashboard } from "./api";

const REFRESH_MS = 60_000;
const DAYS = 14;

function MetricCard({ label, value, hint }) {
  return (
    <article className="metric-card">
      <p>{label}</p>
      <strong>{value ?? "—"}</strong>
      {hint && <small className="muted">{hint}</small>}
    </article>
  );
}

function formatDate(value) {
  if (!value) return "sem registro";
  const date = new Date(`${value.endsWith("Z") || value.includes("+") ? value : `${value}Z`}`);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("pt-BR");
}

export default function App() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState(null);

  const refresh = useCallback(async () => {
    if (!GUILD_ID) {
      setError("Configure VITE_DISCORD_GUILD_ID em dashboard/.env.");
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      setData(await loadDashboard(GUILD_ID, { days: DAYS }));
      setUpdatedAt(new Date());
      setError("");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, REFRESH_MS);
    return () => clearInterval(timer);
  }, [refresh]);

  const metrics = data?.metrics;
  const channels = data?.channels ?? [];
  const timeline = data?.timeline ?? [];

  return (
    <main className="container">
      <header className="topbar">
        <div>
          <span className="eyebrow">SERVER INTELLIGENCE</span>
          <h1>
            Sentinel <span>AI</span>
          </h1>
          <p className="muted">Visão geral da atividade do servidor</p>
        </div>
        <div className="topbar-actions">
          <span className="status">● Monitoramento</span>
          <button type="button" onClick={refresh} disabled={loading}>
            {loading ? "Atualizando..." : "Atualizar"}
          </button>
        </div>
      </header>

      {error && <p className="notice">{error}</p>}

      <section className="metrics-grid">
        <MetricCard
          label="Mensagens registradas"
          value={metrics?.total_messages}
          hint={`${metrics?.messages_last_7d ?? 0} nos últimos 7 dias`}
        />
        <MetricCard
          label="Usuários ativos"
          value={metrics?.active_users}
          hint={`${metrics?.messages_last_24h ?? 0} mensagens em 24h`}
        />
        <MetricCard
          label="Canais ativos"
          value={metrics?.active_channels}
          hint={`última atividade: ${formatDate(metrics?.last_activity)}`}
        />
      </section>

      <section className="panel">
        <span className="eyebrow">TENDÊNCIA</span>
        <h2>Mensagens por dia</h2>
        <ActivityChart timeline={timeline} />
      </section>

      <section className="panel">
        <span className="eyebrow">ENGAJAMENTO</span>
        <h2>Atividade por canal</h2>
        {channels.length === 0 ? (
          <p className="muted">Ainda não há dados para exibir.</p>
        ) : (
          channels.map((channel) => (
            <div className="channel-row" key={channel.channel_id}>
              <div>
                <strong>#{channel.channel_name || channel.channel_id}</strong>
                <small>
                  {channel.unique_authors} participante(s) · última atividade:{" "}
                  {formatDate(channel.last_activity)}
                </small>
              </div>
              <span>{channel.message_count} mensagens</span>
            </div>
          ))
        )}
      </section>

      <footer>
        Sentinel AI · dados agregados, sem conteúdo de mensagens
        {updatedAt && ` · atualizado às ${updatedAt.toLocaleTimeString("pt-BR")}`}
      </footer>
    </main>
  );
}
