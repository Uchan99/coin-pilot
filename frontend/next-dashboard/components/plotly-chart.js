"use client";
import dynamic from "next/dynamic";

/*
 * Plotly 래퍼 — SSR 불가이므로 dynamic import로 클라이언트에서만 로드
 * next/dynamic의 ssr:false 옵션으로 서버 렌더링을 건너뛴다.
 */
const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

export default function PlotlyChart({ data, layout, config, className, style }) {
  const defaultLayout = {
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    font: { family: "Inter", color: "#c2c6d6" },
    margin: { l: 50, r: 20, t: 30, b: 40 },
    xaxis: { gridcolor: "#2a3548", zerolinecolor: "#2a3548" },
    yaxis: { gridcolor: "#2a3548", zerolinecolor: "#2a3548" },
    ...layout,
  };

  const defaultConfig = {
    displayModeBar: false,
    responsive: true,
    ...config,
  };

  return (
    <Plot
      data={data}
      layout={defaultLayout}
      config={defaultConfig}
      className={className}
      style={{ width: "100%", ...style }}
      useResizeHandler
    />
  );
}
