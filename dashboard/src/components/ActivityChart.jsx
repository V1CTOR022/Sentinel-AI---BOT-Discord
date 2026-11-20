// Gráfico de barras em SVG. Sem biblioteca: são poucos pontos e o cálculo
// cabe em vinte linhas.
const WIDTH = 720;
const HEIGHT = 200;
const GAP = 6;

export default function ActivityChart({ timeline }) {
  if (!timeline.length) {
    return <p className="muted">Sem dados no período.</p>;
  }

  const peak = Math.max(...timeline.map((day) => day.message_count), 1);
  const barWidth = Math.max((WIDTH - GAP * timeline.length) / timeline.length, 4);

  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Mensagens por dia">
        {timeline.map((day, index) => {
          const height = Math.max((day.message_count / peak) * (HEIGHT - 28), day.message_count ? 3 : 1);
          const x = index * (barWidth + GAP);
          return (
            <g key={day.day}>
              <rect
                x={x}
                y={HEIGHT - height - 20}
                width={barWidth}
                height={height}
                rx="4"
                fill={day.message_count ? "#9290ff" : "#2a2f42"}
              >
                <title>{`${day.day}: ${day.message_count} mensagens`}</title>
              </rect>
              {index % Math.ceil(timeline.length / 7) === 0 && (
                <text x={x} y={HEIGHT - 4} fontSize="11" fill="#9298ad">
                  {day.day.slice(5)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <figcaption className="muted">Pico de {peak} mensagens em um dia</figcaption>
    </figure>
  );
}
