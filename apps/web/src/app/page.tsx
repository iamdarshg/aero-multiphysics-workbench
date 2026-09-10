'use client';

import dynamic from 'next/dynamic';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Icon } from '../components/icon';
import { checkingApiStatus, probeApi, type ApiStatus } from '../lib/api';
import { getDemoProfile, getDockPanel, getViewModeStatus, qualityGateEvidence, shouldRestoreProvenanceFocus, type DemoId, type DockTab, type ViewMode, updateCouplingStrength } from '../workbench-state';

const EngineeringViewport = dynamic(() => import('../components/engineering-viewport'), { ssr: false, loading: () => <div className="viewport-loading">Preparing code-native geometry…</div> });
const AnalysisCharts = dynamic(() => import('../components/analysis-charts'), { ssr: false, loading: () => <div className="chart-loading">Loading chart renderer…</div> });

const demoOptions: Array<{ id: DemoId; label: string }> = [
  { id: 'edf', label: 'EDF demonstrator' },
  { id: 'aircraft', label: 'Aircraft demonstrator' },
  { id: 'gas-turbine', label: 'Gas turbine demonstrator' },
];

const nodes = ['Physical design state', 'Rotor & duct assembly', 'Motor & ESC', 'Battery pack', 'Inlet flow domain', 'Structure & mounts', 'Thermal network'];
const capabilities = [
  ['OpenMDAO coupling', 'Contract pending'],
  ['OpenFOAM CFD', 'Unavailable'],
  ['Code_Aster FEA', 'Unavailable'],
  ['preCICE exchange', 'Unavailable'],
];
const viewModes: ViewMode[] = ['flow', 'structure', 'thermal', 'fields'];
const dockTabs: Array<{ id: DockTab; label: string; count?: number }> = [
  { id: 'convergence', label: 'Convergence' }, { id: 'energy', label: 'Energy' }, { id: 'resonance', label: 'Resonance' },
  { id: 'timeline', label: 'Timeline' }, { id: 'warnings', label: 'Warnings', count: 2 }, { id: 'logs', label: 'Logs' },
];

export default function WorkbenchPage() {
  const [demoId, setDemoId] = useState<DemoId>('edf');
  const [coupling, setCoupling] = useState(0.9);
  const [expertOpen, setExpertOpen] = useState(false);
  const [dark, setDark] = useState(false);
  const [search, setSearch] = useState('');
  const [activeNode, setActiveNode] = useState('Rotor & duct assembly');
  const [activeView, setActiveView] = useState<ViewMode>('flow');
  const [activeDockTab, setActiveDockTab] = useState<DockTab>('convergence');
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [provenanceOpen, setProvenanceOpen] = useState(false);
  const [apiStatus, setApiStatus] = useState<ApiStatus>(checkingApiStatus);
  const provenanceButtonRef = useRef<HTMLButtonElement>(null);
  const dialogCloseRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const provenanceWasOpen = useRef(false);
  const [history, setHistory] = useState<number[]>([0.9]);
  const [historyIndex, setHistoryIndex] = useState(0);
  const dockTabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const profile = useMemo(() => getDemoProfile(demoId), [demoId]);
  const viewStatus = getViewModeStatus(activeView);
  const dockPanel = getDockPanel(activeDockTab);

  const changeCoupling = useCallback((value: number) => {
    const next = updateCouplingStrength(coupling, value);
    setCoupling(next);
    setHistory((previous) => [...previous.slice(0, historyIndex + 1), next]);
    setHistoryIndex((previous) => previous + 1);
  }, [coupling, historyIndex]);

  const undo = useCallback(() => {
    setHistoryIndex((index) => {
      const next = Math.max(0, index - 1);
      setCoupling(history[next]);
      return next;
    });
  }, [history]);
  const redo = useCallback(() => {
    setHistoryIndex((index) => {
      const next = Math.min(history.length - 1, index + 1);
      setCoupling(history[next]);
      return next;
    });
  }, [history]);

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  }, [dark]);
  useEffect(() => {
    let active = true;
    void probeApi().then((status) => { if (active) setApiStatus(status); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') { event.preventDefault(); if (event.shiftKey) redo(); else undo(); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); document.getElementById('tree-search')?.focus(); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [redo, undo]);

  useEffect(() => {
    if (!provenanceOpen) return;
    dialogCloseRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setProvenanceOpen(false);
      if (event.key === 'Tab') {
        const focusable = dialogRef.current?.querySelectorAll<HTMLElement>('button, input, select, textarea, [href], [tabindex]:not([tabindex="-1"])');
        if (!focusable?.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [provenanceOpen]);

  useEffect(() => {
    if (provenanceOpen) {
      provenanceWasOpen.current = true;
      return;
    }
    if (shouldRestoreProvenanceFocus(provenanceOpen, provenanceWasOpen.current)) {
      provenanceWasOpen.current = false;
      requestAnimationFrame(() => provenanceButtonRef.current?.focus());
    }
  }, [provenanceOpen]);

  const selectDemo = (nextId: DemoId) => {
    const next = getDemoProfile(nextId);
    setDemoId(nextId); setActiveNode(next.activeNode); setCoupling(next.couplingStrength); setHistory([next.couplingStrength]); setHistoryIndex(0);
  };
  const designNodes = useMemo(() => Array.from(new Set([profile.activeNode, ...nodes])), [profile.activeNode]);
  const visibleNodes = designNodes.filter((node) => node.toLowerCase().includes(search.toLowerCase()));
  const focusDockTab = (index: number) => {
    const nextIndex = (index + dockTabs.length) % dockTabs.length;
    setActiveDockTab(dockTabs[nextIndex].id);
    requestAnimationFrame(() => dockTabRefs.current[nextIndex]?.focus());
  };
  const handleDockTabKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') { event.preventDefault(); focusDockTab(index + 1); }
    if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') { event.preventDefault(); focusDockTab(index - 1); }
    if (event.key === 'Home') { event.preventDefault(); focusDockTab(0); }
    if (event.key === 'End') { event.preventDefault(); focusDockTab(dockTabs.length - 1); }
  };

  return <main className="workbench">
    <h1 className="sr-only">Aero Workbench engineering workspace</h1>
    <header className="topbar">
      <div className="brand"><span className="brand-mark">A</span><span>AERO <b>WORKBENCH</b></span></div>
      <div className="design-title"><span className="muted-label">ACTIVE DESIGN</span><strong>{profile.title}</strong><span className="variant">Variant 07 · Baseline</span></div>
      <div className="top-controls">
        <button className="icon-button" aria-label="Undo (Ctrl+Z)" title="Undo (Ctrl+Z)" onClick={undo} disabled={historyIndex === 0}><Icon name="undo" /></button>
        <button className="icon-button" aria-label="Redo (Ctrl+Shift+Z)" title="Redo (Ctrl+Shift+Z)" onClick={redo} disabled={historyIndex === history.length - 1}><Icon name="redo" /></button>
        <label className="demo-select"><span>DEMO</span><select value={demoId} onChange={(e) => selectDemo(e.target.value as DemoId)}>{demoOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></label>
        <button className="theme-toggle" aria-label={dark ? 'Use warm paper theme' : 'Use dark ink theme'} onClick={() => setDark((value) => !value)}>{dark ? 'Use warm paper' : 'Use dark ink'}</button>
      </div>
    </header>
    <section className="coupling-bar">
      <div><span className="muted-label">COMPUTE TARGET</span><strong>Local · {apiStatus.label} · native solver gate closed</strong></div>
      <div className="coupling-control"><div><span className="muted-label">COUPLING STRENGTH</span><strong>{coupling.toFixed(2)} <small>serious engineering</small></strong></div><input aria-label="Coupling strength" type="range" min="0" max="1" step="0.05" value={coupling} onChange={(e) => changeCoupling(Number(e.target.value))} /><span className="coupling-range">0.00 — 1.00</span></div>
      <button className="expert-toggle" onClick={() => setExpertOpen((value) => !value)}>{expertOpen ? 'Hide' : 'Expert'} overrides</button>
      <div className="status" role="status" aria-live="polite"><i /> ANALYTICAL SAMPLE · NATIVE SOLVERS NOT RUN</div>
    </section>
    {expertOpen && <section className="expert-strip"><span>Explicit expert controls</span><label>Interface tolerance <input defaultValue="1.0e-4" /></label><label>Coupling iterations <input type="number" defaultValue="14" /></label><label>Field exchange <select defaultValue="every"><option value="every">Every iteration</option><option>Every 2 iterations</option></select></label><p>Overrides apply to a future solver request; this UI does not execute native solvers.</p></section>}
    <div className="workspace-grid">
      <aside className="left-rail">
        <div className="panel-heading"><div><span className="muted-label">DESIGN TREE</span><strong>Physical state</strong></div><button className="icon-button" aria-label="Focus component search (Ctrl+K)" title="Search parameters (Ctrl+K)" onClick={() => document.getElementById('tree-search')?.focus()}><Icon name="search" /></button></div>
        <input id="tree-search" aria-label="Search design components" className="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search components…" />
        <nav className="tree" aria-label="Design components">{visibleNodes.length > 0 ? visibleNodes.map((node, index) => <button key={node} onClick={() => setActiveNode(node)} className={node === activeNode ? 'selected' : ''}><span className="tree-icon"><Icon name={index === 0 ? 'cube' : index < 4 ? 'ring' : 'node'} /></span>{node}{index === 0 && <span className="node-count">7</span>}</button>) : <div className="empty-state"><Icon name="search" /><b>No components match</b><span>Clear the search to restore the physical design tree.</span><button onClick={() => setSearch('')}>Clear search</button></div>}</nav>
        <div className="rail-divider" />
        <div className="panel-heading compact"><div><span className="muted-label">VARIANTS</span><strong>Design branches</strong></div><button className="icon-button" aria-label="Create a future variant" title="Create a future variant"><Icon name="add" /></button></div>
        <div className="variant-row active"><span>07</span><div><b>Baseline coupling</b><small>Current</small></div><em>0.90</em></div>
        <div className="variant-row"><span>06</span><div><b>Cooling sweep</b><small>Analytical</small></div><em>0.75</em></div>
      </aside>
      <section className="viewport-panel">
        <div className="viewport-toolbar"><div className="viewport-title"><span className="muted-label">GEOMETRY / {profile.geometry}</span><strong>{activeNode}</strong></div><label className="mobile-node-select"><span>Component</span><select value={activeNode} onChange={(event) => setActiveNode(event.target.value)}>{designNodes.map((node) => <option key={node}>{node}</option>)}</select></label><div className="view-modes" role="group" aria-label="Analysis view">{viewModes.map((mode) => { const status = getViewModeStatus(mode); return <button key={mode} className={activeView === mode ? 'active' : ''} aria-pressed={activeView === mode} onClick={() => setActiveView(mode)} title={status.detail}>{status.label}</button>; })}</div><button className="mobile-inspector-toggle" aria-expanded={inspectorOpen} aria-controls="workbench-inspector" onClick={() => setInspectorOpen((value) => !value)}>Parameters</button></div>
        <EngineeringViewport shape={profile.geometry} />
        <div className="viewport-hud"><div><span>VIEW</span><b>ISO · 24°</b></div><div><span>FIELD</span><b>{viewStatus.field}</b></div><div><span>DATA</span><b>{viewStatus.available ? `${profile.evidence.fidelity} sample` : 'Unavailable'}</b></div></div>
        <div className={`sample-notice ${viewStatus.available ? '' : 'blocked-notice'}`} role="status" aria-live="polite">{viewStatus.available ? profile.evidenceLabel : viewStatus.detail}</div>
      </section>
      <aside id="workbench-inspector" className={`right-rail ${inspectorOpen ? 'mobile-open' : ''}`}>
        <div className="panel-heading"><div><span className="muted-label">INSPECTOR</span><strong>{activeNode}</strong></div><div className="inspector-heading-actions"><button className="close-inspector" onClick={() => setInspectorOpen(false)}>Close</button><button className="icon-button" aria-label="Inspector options" title="Inspector options"><Icon name="more" /></button></div></div>
        <div className="inspector-section"><span className="muted-label">PARAMETERS</span><label>Operating RPM <input defaultValue="39,800" /><em>rpm</em></label><label>Inlet Mach <input defaultValue="0.18" /><em>—</em></label><label>Rotor clearance <input defaultValue="0.62" /><em>mm</em></label><label>Coupling strength <input value={coupling.toFixed(2)} onChange={(e) => changeCoupling(Number(e.target.value))} /><em>—</em></label></div>
        <div className="inspector-section"><span className="muted-label">QUALITY GATES</span><div className="quality-row"><i className="good" /><span>Energy balance <small>{qualityGateEvidence.energy}</small></span><b>0.8%</b></div><div className="quality-row"><i className="watch" /><span>Resonance margin <small>{qualityGateEvidence.resonance}</small></span><b>1.21×</b></div><div className="quality-row"><i className="blocked" /><span>Native execution <small>{qualityGateEvidence.native}</small></span><b>Unavailable</b></div></div>
        <button ref={provenanceButtonRef} className="provenance-card" aria-haspopup="dialog" onClick={() => setProvenanceOpen(true)}><span><Icon name="trace" /></span><div><b>Trace sample state</b><small>Provenance · append-only stub</small></div><strong><Icon name="chevron" /></strong></button>
      </aside>
    </div>
    <section className="bottom-dock">
      <div className="dock-tabs" role="tablist" aria-label="Analysis panels">{dockTabs.map((tab, index) => <button key={tab.id} ref={(element) => { dockTabRefs.current[index] = element; }} id={`dock-tab-${tab.id}`} role="tab" aria-controls="analysis-panel" aria-selected={activeDockTab === tab.id} tabIndex={activeDockTab === tab.id ? 0 : -1} className={activeDockTab === tab.id ? 'active' : ''} onClick={() => setActiveDockTab(tab.id)} onKeyDown={(event) => handleDockTabKeyDown(event, index)}>{tab.label} {tab.count ? <span>{tab.count}</span> : null}</button>)}</div>
      <div id="analysis-panel" className="dock-content" role="tabpanel" aria-labelledby={`dock-tab-${activeDockTab}`} tabIndex={0}><div className="chart-card"><div className="chart-meta"><span className="muted-label">{dockPanel.eyebrow}</span><strong>{dockPanel.value}</strong><small>{dockPanel.detail}</small><em>{dockPanel.source} · {dockPanel.fidelity} · {dockPanel.validity}</em></div>{activeDockTab === 'convergence' ? <AnalysisCharts /> : <div className="dock-illustration" aria-hidden="true"><span /><span /><span /><span /><span /></div>}</div><div className="job-card"><span className="muted-label">JOB PROGRESS</span><strong>Analytical state prepared</strong><div className="progress" role="progressbar" aria-label="Analytical sample preparation" aria-valuemin={0} aria-valuemax={100} aria-valuenow={profile.progress}><i style={{ width: `${profile.progress}%` }} /></div><small>{profile.progress}% · no solver process launched</small><button disabled>Request native solve</button></div><div className="warning-card"><div><span className="warning-icon"><Icon name="warning" /></span><b>Mesh suitability needs review</b></div><p>Sample geometry has a duct leading-edge curvature warning. A native mesher is unavailable, so no repair or run can be requested.</p><div><button onClick={() => { setActiveNode('Inlet flow domain'); setInspectorOpen(true); }}>Inspect context</button><button className="link-button" onClick={() => setProvenanceOpen(true)}>View provenance</button></div></div></div>
    </section>
      <footer><span>Keyboard: Ctrl/Cmd + K search · Ctrl/Cmd + Z undo · Ctrl/Cmd + Shift + Z redo · Arrow keys move analysis tabs</span><span role="status" aria-live="polite" title={apiStatus.detail}>{apiStatus.label}; sample-only state; numerical results are never presented as native solver output.</span></footer>
    {provenanceOpen && <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setProvenanceOpen(false); }}><section ref={dialogRef} className="provenance-dialog" role="dialog" aria-modal="true" aria-labelledby="provenance-title" aria-describedby="provenance-description"><div className="dialog-heading"><div><span className="muted-label">STATE RECEIPT</span><h2 id="provenance-title">Analytical sample provenance</h2></div><button ref={dialogCloseRef} className="icon-button" aria-label="Close provenance (Escape)" onClick={() => setProvenanceOpen(false)}><Icon name="close" /></button></div><dl><div><dt>Design</dt><dd>{profile.title}</dd></div><div><dt>Active component</dt><dd>{activeNode}</dd></div><div><dt>Evidence class</dt><dd>Analytical demonstration state</dd></div><div><dt>Source</dt><dd>{profile.evidence.source}</dd></div><div><dt>Fidelity</dt><dd>{profile.evidence.fidelity}</dd></div><div><dt>Validity</dt><dd>{profile.evidence.validity}</dd></div><div><dt>Native execution</dt><dd className="danger-text">{profile.evidence.nativeExecution}</dd></div></dl><div className="capability-list">{capabilities.map(([name, status]) => <div key={name}><span>{name}</span><b className={status === 'Unavailable' ? 'danger-text' : ''}>{status}</b></div>)}</div><p id="provenance-description">This receipt describes local UI sample data only. It is not evidence of a CFD, FEA, thermal, or coupled native solver run.</p><button className="dialog-done" onClick={() => setProvenanceOpen(false)}>Return to workbench</button></section></div>}
  </main>;
}
