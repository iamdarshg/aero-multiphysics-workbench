'use client';

import { useEffect, useRef } from 'react';

declare global { interface Window { Plotly?: { newPlot: (target: HTMLDivElement, data: unknown[], layout: object, config: object) => void; purge: (target: HTMLDivElement) => void } } }

export default function AnalysisCharts() {
  const chart = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let active = true;
    void import('plotly.js-dist-min').then((module) => {
      const plotly = module.default as NonNullable<typeof window.Plotly>;
      if (!active || !chart.current) return;
      plotly.newPlot(chart.current, [{ x: [0, 1, 2, 3, 4, 5, 6], y: [0.22, 0.13, 0.08, 0.045, 0.021, 0.009, 0.0018], type: 'scatter', mode: 'lines', line: { color: '#64d9c7', width: 2.5 }, hovertemplate: 'Iteration %{x}<br>Residual %{y:.3g}<extra></extra>' }], { paper_bgcolor: 'transparent', plot_bgcolor: 'transparent', margin: { l: 36, r: 8, t: 8, b: 25 }, font: { color: '#8da4b6', size: 10 }, xaxis: { showgrid: false, zeroline: false }, yaxis: { type: 'log', gridcolor: '#263b4a', zeroline: false } }, { displayModeBar: false, responsive: true });
    });
    return () => { active = false; if (chart.current && window.Plotly) window.Plotly.purge(chart.current); };
  }, []);
  return <div aria-label="Analytical sample convergence chart; native solver not run" className="analysis-chart" role="img" ref={chart} />;
}
