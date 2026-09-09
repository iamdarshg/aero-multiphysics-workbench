'use client';

import { useEffect, useRef, useState } from 'react';

type PlotlyApi = {
  newPlot: (target: HTMLDivElement, data: unknown[], layout: object, config: object) => void | Promise<unknown>;
  purge: (target: HTMLDivElement) => void | Promise<unknown>;
};

type ChartState = 'idle' | 'loading' | 'ready' | 'error';

export const canInitializeChart = (activated: boolean, visible: boolean, width: number, height: number): boolean =>
  activated && visible && width > 0 && height > 0;

const chartData = [{
  x: [0, 1, 2, 3, 4, 5, 6],
  y: [0.22, 0.13, 0.08, 0.045, 0.021, 0.009, 0.0018],
  type: 'scatter',
  mode: 'lines',
  line: { color: '#64d9c7', width: 2.5 },
  hovertemplate: 'Iteration %{x}<br>Residual %{y:.3g}<extra></extra>',
}];

export default function AnalysisCharts() {
  const shell = useRef<HTMLDivElement>(null);
  const chart = useRef<HTMLDivElement>(null);
  const plotly = useRef<PlotlyApi | null>(null);
  const [visible, setVisible] = useState(false);
  const [activated, setActivated] = useState(false);
  const [retry, setRetry] = useState(0);
  const [state, setState] = useState<ChartState>('idle');

  useEffect(() => {
    const element = shell.current;
    if (!element) return;
    if (!('IntersectionObserver' in window)) {
      setVisible(true);
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        setVisible(true);
        observer.disconnect();
      }
    }, { rootMargin: '160px' });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!visible || !activated) return;
    let disposed = false;
    const load = async () => {
      setState('loading');
      try {
        const module = await import('plotly.js-dist-min');
        if (disposed || !chart.current) return;
        const candidate = module.default as PlotlyApi;
        const target = chart.current;
        await new Promise<void>((resolve) => window.requestAnimationFrame(() => resolve()));
        const bounds = target.getBoundingClientRect();
        if (!canInitializeChart(activated, visible, bounds.width, bounds.height)) {
          if (!disposed) setState('idle');
          return;
        }
        plotly.current = candidate;
        await Promise.resolve(candidate.newPlot(target, chartData, {
          paper_bgcolor: 'transparent',
          plot_bgcolor: 'transparent',
          margin: { l: 36, r: 8, t: 8, b: 25 },
          font: { color: '#8da4b6', size: 10 },
          xaxis: { showgrid: false, zeroline: false },
          yaxis: { type: 'log', gridcolor: '#263b4a', zeroline: false },
        }, { displayModeBar: false, responsive: true }));
        if (disposed) return;
        setState('ready');
      } catch {
        if (!disposed) setState('error');
      }
    };
    void load();
    return () => {
      disposed = true;
      const target = chart.current;
      const candidate = plotly.current;
      plotly.current = null;
      if (target && candidate) void Promise.resolve(candidate.purge(target));
    };
  }, [activated, retry, visible]);

  return <div ref={shell} className="chart-shell">
    <div ref={chart} aria-label="Analytical sample convergence chart; native solver not run" className="analysis-chart" role="img" aria-hidden={state !== 'ready'} />
    {state === 'idle' && <button className="chart-action" onClick={() => setActivated(true)}>Load analytical chart</button>}
    {state === 'loading' && <div className="chart-status" role="status">Loading analytical chart…</div>}
    {state === 'error' && <div className="chart-status chart-error" role="alert"><span>Chart renderer unavailable.</span><button className="chart-action" onClick={() => setRetry((value) => value + 1)}>Retry chart</button></div>}
  </div>;
}
