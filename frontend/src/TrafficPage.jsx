import { useState } from "react";
import { PatternCards, RequestTable, SignalHelp, SourceFilter } from "./MonitoringCommon";
import { post, requestJson, sourceLabel, timestamp, useMonitor } from "./monitoringApi";
import "./SentinelPanel.css";

export default function TrafficPage({ apiUrl, onView, onChanged, onTest }) {
  const [source, setSource] = useState("all");
  const [scale, setScale] = useState("minute");
  const [selection, setSelection] = useState(null);
  const [research, setResearch] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [scenario, setScenario] = useState("ring");
  const [count, setCount] = useState(10);
  const { data, error: loadError, refresh } = useMonitor(apiUrl, `/monitoring/traffic?source=${source}&scale=${scale}`);
  const selected = data?.buckets.find((bucket) => bucket.start === selection) || data?.buckets.at(-1);

  async function action(callback) {
    setBusy(true); setError(""); setNotice("");
    try { await callback(); }
    catch (failure) { setError(failure.message); }
    finally { await refresh(); setBusy(false); }
  }

  function changeView(update, value) { update(value); setSelection(null); setResearch(null); setError(""); setNotice(""); }

  return <section className="sentinel content-card" id="traffic-monitor">
    <div className="card-header sentinel-heading"><div><p className="eyebrow">REQUEST TRAFFIC</p><h3>How many return requests are coming in?</h3><p>Watch new requests arrive. Choose a busy period to check what the requests have in common.</p></div><span className="source-badge">UPDATES EVERY 5 SECONDS</span></div>
    <div className="sentinel-body">
      <ol className="monitor-steps" aria-label="How to use this page">
        <li><strong>1. Watch requests</strong><span>Each bar shows how many arrived.</span></li>
        <li><strong>2. Check a busy period</strong><span>Click a bar, then check its requests.</span></li>
        <li><strong>3. Pause only if needed</strong><span>You choose whether to stop new requests.</span></li>
      </ol>
      <div className="sentinel-controls"><SourceFilter value={source} onChange={(value) => changeView(setSource, value)} disabled={busy} /><label>Time range<select aria-label="Time range" disabled={busy} value={scale} onChange={(event) => changeView(setScale, event.target.value)}><option value="minute">Last hour · minute by minute</option><option value="five_minutes">Last 6 hours · every 5 minutes</option><option value="hour">Last 24 hours · hour by hour</option></select></label><button className="secondary-button" onClick={() => refresh()}>Refresh now</button></div>
      {(error || loadError) && <div className="form-message error" role="alert">{error || loadError}</div>}
      {notice && <p className="sentinel-notice" role="status">{notice}</p>}
      {!data ? <p>Loading incoming request traffic…</p> : <><div className="sentinel-stats"><div><span>Total requests</span><strong>{data.request_count}</strong><small>Customer and test attempts in this view</small></div><div><span>Test requests</span><strong>{data.demo_count}</strong><small>Included in the total, not real customers</small></div><div><span>Blocked while paused</span><strong>{data.paused_count}</strong><small>Still counted so you can watch activity</small></div><div><span>Busy periods to check</span><strong className="sentinel-warning">{data.buckets.filter((bucket) => bucket.spike).length}</strong><small>High volume, not confirmed fraud</small></div></div>
        <TrafficChart buckets={data.buckets} selected={selected?.start} onSelect={(bucket) => { setSelection(bucket.start); setResearch(null); }} scale={scale} />
        <p className="sentinel-disclaimer">A busy period is not proof of fraud. Nothing is blocked unless you choose to pause new requests.</p>
        {data.request_count === 0 && <div className="sentinel-empty"><strong>Your graph is ready</strong><p>No requests in this time range yet. Use the test controls below, or create one custom test to see your first bar.</p><button className="secondary-button" onClick={onTest}>Create a test request</button></div>}
        <details className="monitor-help"><summary>How are busy periods highlighted?</summary><p>{data.note}</p><p>The newest bar is still growing. Blocked attempts are included in the total, so you can see whether requests keep arriving during a pause.</p></details><p className="pattern-time">Updated {timestamp(data.checked_at)} · Test requests are included unless filtered out. The latest bar is still updating.</p>
        {selected && <div className="traffic-selection"><div><p className="eyebrow">SELECTED TIME{selected.spike ? " · HIGH REQUEST VOLUME" : ""}</p><h4>{timestamp(selected.start)} → {timestamp(selected.end)}</h4><p>{selected.count} requests · {selected.live} customer · {selected.demo} test · {selected.paused} blocked while paused. Average in earlier periods: {selected.baseline}.</p></div><div className="header-actions"><button className="primary-button" disabled={busy || !!loadError} onClick={() => action(async () => { const result = await requestJson(`${apiUrl}/monitoring/traffic/research`, post({ source, start: selected.start, end: selected.end })); setResearch(result); })}>{busy ? "Working…" : "Check these requests"}</button><button className="secondary-button" disabled={busy || !!loadError} onClick={() => action(async () => { const result = await requestJson(`${apiUrl}/monitoring/traffic/research`, post({ source, start: data.window_start, end: data.buckets.at(-1).end })); setResearch(result); })}>Check all requests on this chart</button></div></div>}
        {research && <section className="traffic-research" aria-label="Request research results"><p className="eyebrow">YOUR REQUEST CHECK</p><h4>Here is what we found</h4><p>We checked <strong>{research.request_count} requests</strong> and found <strong>{research.patterns.length} matching groups</strong>. {research.patterns.length ? "Open a group below to see which details match." : "No repeated customer, device, IP, location or reference was found in the details provided."}</p><small>{timestamp(research.start)} → {timestamp(research.end)} · Checked at {timestamp(research.researched_at)}</small><p>This check compares the details supplied with each request. Matches can be legitimate; review the requests before taking action.</p><PatternCards patterns={research.patterns} onView={onView} /><SignalHelp /><details><summary>All {research.request_count} requests examined</summary><RequestTable requests={research.requests} onView={onView} /></details></section>}
        <IntakeControls data={data} disabled={busy || !!loadError} onPause={(payload) => action(async () => { await requestJson(`${apiUrl}/monitoring/intake/pauses`, post(payload)); setNotice("New requests are paused. Existing returns and refunds are unchanged."); })} onResume={(id) => action(async () => { await requestJson(`${apiUrl}/monitoring/intake/pauses/${id}/resume`, post({})); setNotice("This pause has ended. If another pause is still active, it will continue to block matching requests."); })} />
      </>}
      <div className="sentinel-demo"><p className="eyebrow">TRY A DEMO</p><h4>See how it works with test requests</h4><p>Choose a sample and send a few test requests. They appear on this graph just like customer requests, clearly marked as tests.</p><div className="sentinel-controls"><label>Test scenario<select aria-label="Test scenario" disabled={busy} value={scenario} onChange={(event) => setScenario(event.target.value)}><option value="ring">Different accounts using the same device and IP</option><option value="ip">Same IP</option><option value="device">Same device</option><option value="account">Same account</option><option value="location">Same city or region</option><option value="normal">Different customers with no shared details</option></select></label><label>Number of test requests<input aria-label="Number of test requests" type="number" min="1" max="100" value={count} onChange={(event) => setCount(event.target.value)} /></label><button disabled={busy || !Number.isInteger(Number(count)) || Number(count) < 1 || Number(count) > 100} className="primary-button" onClick={() => action(async () => { const result = await requestJson(`${apiUrl}/monitoring/sentinel/demo`, post({ scenario, count: Number(count) })); setSource("all"); setSelection(null); setNotice(`${result.case_ids.length} test requests added. Select the new bar and click Check these requests to see what they share.`); await onChanged(); })}>Send test requests</button><button className="secondary-button" disabled={busy} onClick={onTest}>Create one custom test</button></div></div>
    </div>
  </section>;
}

function TrafficChart({ buckets, selected, onSelect, scale }) {
  const width = 1000, height = 300, left = 50, bottom = 260, top = 20;
  const maximum = Math.max(5, ...buckets.map((bucket) => Math.max(bucket.count, bucket.baseline)));
  const step = (width - left - 20) / buckets.length;
  const y = (value) => bottom - value / maximum * (bottom - top);
  return <div className="traffic-chart"><div className="traffic-legend"><span><i className="live" />Customer requests</span><span><i className="demo" />Test requests</span><span><i className="spike" />High request volume</span><span><i className="paused" />Includes requests blocked by a pause</span></div><svg viewBox={`0 0 ${width} ${height}`} aria-label="Incoming request counts over time" role="group">
    {[0, .25, .5, .75, 1].map((fraction) => <g key={fraction}><line x1={left} x2={width - 20} y1={y(maximum * fraction)} y2={y(maximum * fraction)} stroke="#2d3941" /><text x={left - 10} y={y(maximum * fraction) + 4} textAnchor="end" fill="#9cabb5" fontSize="11">{Number((maximum * fraction).toFixed(1))}</text></g>)}
    {buckets.map((bucket, index) => <g key={bucket.start} role="button" tabIndex="0" aria-label={`${timestamp(bucket.start)}: ${bucket.count} requests, ${bucket.demo} test, ${bucket.paused} blocked while paused${bucket.spike ? ', high request volume' : ''}`} aria-pressed={selected === bucket.start} onClick={() => onSelect(bucket)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(bucket); } }}>
      <title>{timestamp(bucket.start)}: {bucket.count} incoming requests ({bucket.live} customer / {bucket.demo} test); {bucket.paused} blocked while paused</title>
      <rect x={left + index * step} y={top} width={step} height={bottom - top} fill={selected === bucket.start ? "#d5e4ed" : "transparent"} fillOpacity={selected === bucket.start ? .08 : 1} />
      <rect x={left + index * step + 1} y={y(bucket.live)} width={Math.max(1, step - 2)} height={bottom - y(bucket.live)} fill="#64c3bb" />
      <rect x={left + index * step + 1} y={y(bucket.count)} width={Math.max(1, step - 2)} height={y(bucket.live) - y(bucket.count)} fill="#a897e8" />
      {bucket.spike && <rect x={left + index * step + 1} y={y(bucket.count)} width={Math.max(1, step - 2)} height={bottom - y(bucket.count)} fill="none" stroke="#ffbd6d" strokeWidth="2" />}
      {bucket.paused > 0 && <circle cx={left + (index + .5) * step} cy={Math.max(10, y(bucket.count) - 6)} r="3" fill="#f37d88" />}
      {index % Math.ceil(buckets.length / 6) === 0 && <text x={left + (index + .5) * step} y={bottom + 22} textAnchor="middle" fill="#a9b8c2" fontSize="11">{new Date(bucket.start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</text>}
    </g>)}
    <text x={width - 20} y={height - 1} textAnchor="end" fill="#a9b8c2" fontSize="11">{scale === "hour" ? "Requests per hour" : scale === "five_minutes" ? "Requests per 5 minutes" : "Requests per minute"} · local time · click a bar to inspect</text>
  </svg></div>;
}

function IntakeControls({ data, disabled, onPause, onResume }) {
  const [scope, setScope] = useState("all");
  const [duration, setDuration] = useState(15);
  const [reason, setReason] = useState("Checking an unusual number of return requests");
  const [confirming, setConfirming] = useState(false);
  const [resumeId, setResumeId] = useState(null);
  return <section className="sentinel-pause"><p className="eyebrow">OPTIONAL · YOU ARE IN CONTROL</p><h4>Pause new requests</h4><p>Temporarily stop accepting new returns while you investigate. Existing returns and refunds continue as before. Customers can try again when the pause ends.</p>
    {data.active_pauses.map((pause) => <div className="sentinel-hold" key={pause.id}><div><strong>{sourceLabel(pause.scope)} paused</strong><p>Until {timestamp(pause.expires_at)} · {pause.reason}</p>{resumeId === pause.id && <p>End this pause now? Any other active pauses will stay in place.</p>}</div>{resumeId === pause.id ? <div className="header-actions"><button disabled={disabled} className="primary-button" onClick={() => { setResumeId(null); onResume(pause.id); }}>Yes, resume requests</button><button className="secondary-button" onClick={() => setResumeId(null)}>Cancel</button></div> : <button disabled={disabled} className="secondary-button" onClick={() => setResumeId(pause.id)}>Resume requests</button>}</div>)}
    <div className="sentinel-controls"><label>Which requests?<select aria-label="Which requests?" disabled={disabled} value={scope} onChange={(event) => { setScope(event.target.value); setConfirming(false); }}><option value="all">Customer + test requests</option><option value="demo">Test requests only</option><option value="live">Customer requests only</option></select></label><label>Pause for<select aria-label="Pause for" disabled={disabled} value={duration} onChange={(event) => { setDuration(Number(event.target.value)); setConfirming(false); }}>{[5, 15, 30, 60].map((value) => <option key={value} value={value}>{value} minutes</option>)}</select></label><label>Reason<input aria-label="Pause reason" value={reason} maxLength={500} onChange={(event) => { setReason(event.target.value); setConfirming(false); }} /></label><button disabled={disabled || reason.trim().length < 3} className="secondary-button" onClick={() => setConfirming(true)}>Review pause</button></div>
    {confirming && <div className="sentinel-confirm" role="group" aria-label="Confirm request pause"><strong>Pause {scope === "all" ? "customer and test" : scope === "demo" ? "test" : "customer"} requests for {duration} minutes?</strong><p>New returns will not be accepted during this time. Customers can try again afterwards. Existing cases are unchanged, and you can end the pause early.</p><div className="header-actions"><button disabled={disabled} className="primary-button" onClick={() => { setConfirming(false); onPause({ scope, duration_minutes: duration, reason: reason.trim() }); }}>Yes, pause new requests</button><button className="secondary-button" onClick={() => setConfirming(false)}>Cancel</button></div></div>}
    {data.pause_history.length > 0 && <details className="sentinel-history"><summary>Past pauses</summary>{data.pause_history.map((pause) => <div key={pause.id}><strong>#{pause.id} · {pause.status === "ACTIVE" ? "Active" : pause.status === "RESUMED" ? "Ended early" : "Finished"} · {sourceLabel(pause.scope)}</strong><span>{timestamp(pause.created_at)} → {timestamp(pause.expires_at)}</span><p>{pause.reason}</p></div>)}</details>}
  </section>;
}
