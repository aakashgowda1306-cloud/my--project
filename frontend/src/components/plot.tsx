"use client";

import { useEffect, useRef } from "react";
import type { Config, Data, Layout } from "plotly.js-dist-min";

/** Thin Plotly wrapper. Plotly is large, so it is loaded only in the browser, only when a chart is shown. */
export function Plot({ data, layout, ariaLabel, height = 260 }: {
  data: Data[]; layout?: Partial<Layout>; ariaLabel: string; height?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    const el = ref.current;
    import("plotly.js-dist-min").then((Plotly) => {
      if (cancelled || !el) return;
      const base: Partial<Layout> = {
        height, margin: { l: 36, r: 8, t: 8, b: 32 }, paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
        font: { family: "IBM Plex Sans, system-ui, sans-serif", color: "#8fa3c0", size: 12 },
        xaxis: { gridcolor: "#1a2e50", zeroline: false, fixedrange: true },
        yaxis: { gridcolor: "#1a2e50", zeroline: false, fixedrange: true },
        legend: { orientation: "h", y: -0.18 }, hoverlabel: { bgcolor: "#15294a", bordercolor: "#22385e", font: { color: "#e6edf7" } },
      };
      const config: Partial<Config> = { displayModeBar: false, responsive: true };
      Plotly.react(el, data, { ...base, ...layout }, config);
    });
    return () => { cancelled = true; };
  }, [data, layout, height]);

  useEffect(() => () => {
    const el = ref.current;
    if (el) import("plotly.js-dist-min").then((Plotly) => Plotly.purge(el));
  }, []);

  return <div ref={ref} role="img" aria-label={ariaLabel} style={{ minHeight: height }} />;
}
