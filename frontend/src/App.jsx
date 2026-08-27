import { useCallback, useEffect, useState } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

function App() {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCase, setSelectedCase] = useState(null);
  const [activePage, setActivePage] = useState("overview");
  const [showTestCase, setShowTestCase] = useState(false);
  const [modelInfo, setModelInfo] = useState(null);
  const [feedback, setFeedback] = useState(null);

  useEffect(() => {
    fetchCases();
    fetchModelStatus();
    fetchFeedback();
  }, []);

  async function fetchModelStatus() {
    try {
      const response = await fetch(`${API_URL}/model/status`);
      const data = await response.json();
      if (response.ok) setModelInfo(data.model);
    } catch (error) {
      console.error("Failed to fetch model status:", error);
    }
  }

  async function fetchFeedback() {
    try {
      const response = await fetch(`${API_URL}/feedback/summary`);
      const data = await response.json();
      if (response.ok) setFeedback(data);
    } catch (error) { console.error("Failed to fetch feedback:", error); }
  }

  async function fetchCases() {
    try {
      const response = await fetch(`${API_URL}/cases`);
      const data = await response.json();

      setCases(data.cases || []);
    } catch (error) {
      console.error("Failed to fetch cases:", error);
    } finally {
      setLoading(false);
    }
  }

  const highRisk = cases.filter((item) => item.risk_level === "HIGH").length;
  const mediumRisk = cases.filter((item) => item.risk_level === "MEDIUM").length;
  const lowRisk = cases.filter((item) => item.risk_level === "LOW").length;
  const pageTitle = activePage === "settings" ? "Model Settings" : activePage === "analytics" ? "Risk Analytics" : activePage === "cases" ? "Risk Cases" : "Risk Overview";

  function navigate(page, sectionId) {
    setActivePage(page);
    window.setTimeout(() => sectionId ? document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth", block: "start" }) : window.scrollTo({ top: 0, behavior: "smooth" }), 0);
  }

  return (
    <div className="app">

      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">◆</div>
          <div>
            <h1>Risk Manager</h1>
            <span>AI Commerce Security</span>
          </div>
        </div>
        <nav>
          <button className={`nav-item ${activePage === "overview" ? "active" : ""}`} onClick={() => navigate("overview")}><span>▦</span>Overview</button>
          <button className={`nav-item ${activePage === "analytics" ? "active" : ""}`} onClick={() => navigate("analytics", "risk-analytics")}><span>⌁</span>Analytics</button>
          <button className={`nav-item ${activePage === "cases" ? "active" : ""}`} onClick={() => navigate("cases", "recent-cases")}><span>◉</span>Risk Cases</button>
          <button className={`nav-item ${activePage === "settings" ? "active" : ""}`} onClick={() => setActivePage("settings")}><span>⚙</span>Settings</button>
        </nav>
        <div className="sidebar-bottom">
          <div className="system-status">
            <span className="status-dot"></span>
            <div>
              <strong>System Online</strong>
              <small>Model API connected</small>
            </div>
          </div>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div>
            <p className="eyebrow">MERCHANT CONSOLE</p>
            <h2>{pageTitle}</h2>
            <p className="page-description">{activePage === "settings" ? "Training data, cost assumptions and model controls" : "Live return-abuse monitoring and decision support"}</p>
          </div>
          <div className="topbar-right">
            <div className="model-status">
              <span className="pulse"></span>
              {modelInfo?.model_source === "merchant_trained" ? "Merchant Model Active" : "Synthetic Baseline Active"}
            </div>
            <div className="avatar">PM</div>
          </div>
        </header>
        {activePage === "settings" ? (
          <SettingsPage modelInfo={modelInfo} onTrained={setModelInfo} />
        ) : (
          <Overview cases={cases} loading={loading} fetchCases={fetchCases} onView={setSelectedCase} onTest={() => setShowTestCase(true)} highRisk={highRisk} mediumRisk={mediumRisk} lowRisk={lowRisk} modelInfo={modelInfo} feedback={feedback} />
        )}
      </main>
      {selectedCase && <CasePanel key={selectedCase} caseId={selectedCase} onClose={() => setSelectedCase(null)} onCaseUpdated={() => Promise.all([fetchCases(), fetchFeedback()])} />}
      {showTestCase && <TestCasePanel onClose={() => setShowTestCase(false)} onCreated={async (id) => { setShowTestCase(false); await fetchCases(); setSelectedCase(id); }} />}
    </div>
  );
}

function Overview({ cases, loading, fetchCases, onView, onTest, highRisk, mediumRisk, lowRisk, modelInfo, feedback }) {
  const metrics = modelInfo?.metrics;
  const thresholds = modelInfo?.routing_thresholds;
  const matrix = modelInfo?.confusion_matrix;
  const costs = modelInfo?.cost_analysis;
  const impact = modelInfo?.business_impact;
  return <>
    <section className="stats-grid">
      <StatCard title="Total Cases" value={cases.length} subtitle="All return requests" type="neutral" />
      <StatCard title="High Risk" value={highRisk} subtitle="Requires attention" type="high" />
      <StatCard title="Medium Risk" value={mediumRisk} subtitle="Evidence recommended" type="medium" />
      <StatCard title="Low Risk" value={lowRisk} subtitle="Auto-approvable" type="low" />
    </section>
    {feedback && <section className="feedback-strip"><div><span>Verified outcomes</span><strong>{feedback.verified_cases}</strong></div><div><span>Recommendation disagreement</span><strong>{(feedback.recommendation_disagreement_rate * 100).toFixed(1)}%</strong></div><div><span>Estimated loss prevented</span><strong>{formatCurrency(feedback.estimated_loss_prevented)}</strong></div><div><span>Estimated loss realized</span><strong>{formatCurrency(feedback.estimated_loss_realized)}</strong></div></section>}
    <AnalyticsSection cases={cases} highRisk={highRisk} mediumRisk={mediumRisk} lowRisk={lowRisk} modelInfo={modelInfo} />
    <section className="content-card" id="recent-cases">
      <div className="card-header">
        <div><p className="eyebrow">LIVE QUEUE</p><h3>Recent Risk Cases</h3></div>
        <div className="header-actions"><button className="refresh-button" onClick={fetchCases}>↻ Refresh</button><button className="primary-button" onClick={onTest}>＋ Test a case</button></div>
      </div>
      {loading ? <div className="empty-state">Loading risk cases...</div> : cases.length === 0 ? <div className="empty-state"><div className="empty-icon">◌</div><h3>No cases yet</h3><p>Test a return-risk case to see it here.</p><button className="primary-button" onClick={onTest}>Test your first case</button></div> : <div className="table-wrapper"><table><thead><tr><th>CASE</th><th>RISK SCORE</th><th>LEVEL</th><th>CLAIM</th><th>ORDER VALUE</th><th>ACTION</th><th></th></tr></thead><tbody>{cases.map((item) => <tr key={item.id}><td><strong>#{String(item.id).padStart(4, "0")}</strong><small>{formatDate(item.created_at)}</small></td><td><strong className="score">{Number(item.risk_score).toFixed(1)}%</strong></td><td><RiskBadge level={item.risk_level} /></td><td>{formatClaim(item.claim_type)}</td><td>₹{Number(item.order_value).toLocaleString()}</td><td><span className="action-text">{formatAction(item.recommended_action)}</span></td><td><button className="view-button" onClick={() => onView(item.id)}>View →</button></td></tr>)}</tbody></table></div>}
    </section>
    <section className="bottom-grid">
      <div className="info-card"><div className="model-title-row"><div><p className="eyebrow">MODEL</p><h3>XGBoost Risk Engine</h3></div><span className={`source-badge ${modelInfo?.model_source === "merchant_trained" ? "merchant" : "synthetic"}`}>{modelInfo?.model_source === "merchant_trained" ? "MERCHANT-TRAINED" : "SYNTHETIC DATA"}</span></div><p>{modelInfo?.model_source === "merchant_trained" ? `Trained from ${modelInfo.dataset_name}.` : "Baseline trained from reproducible synthetic return cases; not real merchant history."}</p><div className="model-metrics"><div><span>ROC-AUC</span><strong>{metrics ? metrics.roc_auc.toFixed(4) : "—"}</strong></div><div><span>Precision</span><strong>{metrics ? `${(metrics.precision * 100).toFixed(1)}%` : "—"}</strong></div><div><span>Recall</span><strong>{metrics ? `${(metrics.recall * 100).toFixed(1)}%` : "—"}</strong></div></div></div>
      <div className="info-card"><p className="eyebrow">DECISION ENGINE</p><h3>Cost-selected routing</h3><div className="routing-row"><RiskBadge level="LOW" /><span>&lt; {thresholds ? `${(thresholds.low * 100).toFixed(0)}%` : "—"}</span><strong>Auto Approve</strong></div><div className="routing-row"><RiskBadge level="MEDIUM" /><span>{thresholds ? `${(thresholds.low * 100).toFixed(0)}–${(thresholds.high * 100).toFixed(0)}%` : "—"}</span><strong>Request Evidence</strong></div><div className="routing-row"><RiskBadge level="HIGH" /><span>≥ {thresholds ? `${(thresholds.high * 100).toFixed(0)}%` : "—"}</span><strong>Manual Review</strong></div></div>
    </section>
    {matrix && costs && <section className="evaluation-card"><div className="evaluation-heading"><div><p className="eyebrow">HELD-OUT EVALUATION</p><h3>Confusion matrix & merchant cost</h3></div><span>{modelInfo.test_rows.toLocaleString()} unseen test cases</span></div><div className="evaluation-content"><div className="confusion-wrap"><div className="axis-label">Predicted outcome →</div><div className="confusion-matrix"><div className="matrix-corner">Actual ↓</div><div className="matrix-head">Legitimate</div><div className="matrix-head">Abuse</div><div className="matrix-head row-head">Legitimate</div><MatrixCell label="True negative" value={matrix.tn} type="correct" /><MatrixCell label="False positive" value={matrix.fp} type="warning" /><div className="matrix-head row-head">Abuse</div><MatrixCell label="False negative" value={matrix.fn} type="danger" /><MatrixCell label="True positive" value={matrix.tp} type="correct" /></div></div><div className="cost-summary"><p className="eyebrow">FALSE-POSITIVE COST</p><strong>{formatCurrency(costs.false_positive_cost)}</strong><span>{matrix.fp.toLocaleString()} legitimate cases × {formatCurrency(costs.false_positive_unit_cost)}</span><div className="cost-divider"></div><div><span>Missed-abuse cost</span><b>{formatCurrency(costs.false_negative_cost)}</b></div><div><span>Total expected cost</span><b>{formatCurrency(costs.total_cost)}</b></div><small>Calculated at the cost-selected {Math.round(thresholds.high * 100)}% review threshold.</small></div></div>{impact && <div className="impact-comparison"><ImpactCard label="Approve everything" value={impact.approve_all_cost} /><ImpactCard label="Review everything" value={impact.review_all_cost} /><ImpactCard label="AI routing policy" value={impact.ai_policy_cost} active /><div className={`savings-callout ${impact.savings_vs_best_baseline >= 0 ? "positive" : "negative"}`}><span>Estimated savings vs best simple policy</span><strong>{formatCurrency(impact.savings_vs_best_baseline)}</strong><small>Held-out estimate using the costs configured in Settings.</small></div></div>}</section>}
  </>;
}

function MatrixCell({ label, value, type }) { return <div className={`matrix-cell ${type}`}><strong>{value.toLocaleString()}</strong><span>{label}</span></div>; }
function ImpactCard({ label, value, active }) { return <div className={`impact-card ${active ? "active" : ""}`}><span>{label}</span><strong>{formatCurrency(value)}</strong></div>; }

function AnalyticsSection({ cases, highRisk, mediumRisk, lowRisk, modelInfo }) {
  return <section className="analytics-section" id="risk-analytics">
    <div className="section-heading"><div><p className="eyebrow">RISK ANALYTICS</p><h3>Signals at a glance</h3></div><span className="data-chip"><i></i>{cases.length} live cases</span></div>
    <div className="analytics-grid">
      <RiskDonut total={cases.length} high={highRisk} medium={mediumRisk} low={lowRisk} />
      <ScoreHistogram cases={cases} />
      <MetricBars metrics={modelInfo?.metrics} />
      <CostCurve points={modelInfo?.cost_curve || []} selectedThreshold={modelInfo?.routing_thresholds?.high} />
    </div>
  </section>;
}

function RiskDonut({ total, high, medium, low }) {
  const highEnd = total ? (high / total) * 100 : 0;
  const mediumEnd = total ? highEnd + (medium / total) * 100 : 0;
  const background = total ? `conic-gradient(#c96861 0 ${highEnd}%, #caa45f ${highEnd}% ${mediumEnd}%, #65b681 ${mediumEnd}% 100%)` : "#292f34";
  return <div className="chart-card"><div className="chart-title"><div><span>CASE MIX</span><h4>Risk distribution</h4></div><span>LIVE</span></div><div className="donut-content"><div className="donut" style={{ background }} role="img" aria-label={`${high} high, ${medium} medium and ${low} low risk cases`}><div><strong>{total}</strong><span>CASES</span></div></div><div className="chart-legend"><Legend color="high" label="High risk" value={high} total={total} /><Legend color="medium" label="Medium risk" value={medium} total={total} /><Legend color="low" label="Low risk" value={low} total={total} /></div></div></div>;
}

function Legend({ color, label, value, total }) { return <div><i className={color}></i><span>{label}</span><strong>{total ? `${((value / total) * 100).toFixed(0)}%` : "0%"}</strong><small>{value} cases</small></div>; }

function ScoreHistogram({ cases }) {
  const bands = [[0, 20], [20, 40], [40, 60], [60, 80], [80, 101]].map(([start, end]) => ({ label: `${start}–${end === 101 ? 100 : end}%`, count: cases.filter((item) => Number(item.risk_score) >= start && Number(item.risk_score) < end).length }));
  const maximum = Math.max(1, ...bands.map((band) => band.count));
  return <div className="chart-card"><div className="chart-title"><div><span>SCORE BANDS</span><h4>Case frequency</h4></div><span>COUNT</span></div><div className="histogram" role="img" aria-label="Risk score histogram">{bands.map((band) => <div key={band.label}><strong>{band.count}</strong><div><i style={{ height: `${Math.max(4, (band.count / maximum) * 100)}%` }} title={`${band.label}: ${band.count} cases`}></i></div><span>{band.label}</span></div>)}</div></div>;
}

function MetricBars({ metrics }) {
  const rows = [["Precision", metrics?.precision], ["Recall", metrics?.recall], ["F1 score", metrics?.f1], ["Accuracy", metrics?.accuracy]];
  return <div className="chart-card"><div className="chart-title"><div><span>HELD-OUT MODEL</span><h4>Performance profile</h4></div><span>{metrics ? `AUC ${metrics.roc_auc.toFixed(3)}` : "NO DATA"}</span></div><div className="metric-bars">{rows.map(([label, value]) => <div key={label}><div><span>{label}</span><strong>{value == null ? "—" : `${(value * 100).toFixed(1)}%`}</strong></div><section><i style={{ width: `${(value || 0) * 100}%` }}></i></section></div>)}</div></div>;
}

function CostCurve({ points, selectedThreshold }) {
  const width = 560, height = 190, padX = 34, padY = 25;
  const maxCost = Math.max(1, ...points.map((point) => point.total_cost));
  const coordinates = points.map((point, index) => ({ ...point, x: padX + (index / Math.max(1, points.length - 1)) * (width - padX * 2), y: height - padY - (point.total_cost / maxCost) * (height - padY * 2) }));
  const line = coordinates.map((point, index) => `${index ? "L" : "M"}${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");
  const area = coordinates.length ? `${line} L${coordinates.at(-1).x},${height - padY} L${coordinates[0].x},${height - padY} Z` : "";
  const selected = coordinates.reduce((closest, point) => !closest || Math.abs(point.threshold - selectedThreshold) < Math.abs(closest.threshold - selectedThreshold) ? point : closest, null);
  return <div className="chart-card cost-curve-card"><div className="chart-title"><div><span>THRESHOLD ECONOMICS</span><h4>Expected cost curve</h4></div><span>{selected ? `SELECTED ${Math.round(selected.threshold * 100)}%` : "NO DATA"}</span></div>{points.length ? <><svg className="cost-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Expected merchant cost by review threshold"><defs><linearGradient id="costArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#c6a363" stopOpacity=".26"/><stop offset="100%" stopColor="#c6a363" stopOpacity="0"/></linearGradient></defs><line x1={padX} y1={height-padY} x2={width-padX} y2={height-padY} className="chart-axis"/><path d={area} fill="url(#costArea)"/><path d={line} className="cost-line"/>{coordinates.map((point) => <circle key={point.threshold} cx={point.x} cy={point.y} r={point === selected ? 5 : 2.3} className={point === selected ? "selected-point" : "curve-point"}><title>{Math.round(point.threshold * 100)}% threshold: {formatCurrency(point.total_cost)}</title></circle>)}<text x={padX} y={height-7}>5%</text><text x={width-padX} y={height-7} textAnchor="end">95%</text><text x={padX} y={13}>{formatCompactCurrency(maxCost)}</text></svg><div className="curve-summary"><div><span>Minimum expected cost</span><strong>{formatCurrency(selected?.total_cost)}</strong></div><div><span>False positives</span><strong>{selected?.false_positives.toLocaleString()}</strong></div><div><span>False negatives</span><strong>{selected?.false_negatives.toLocaleString()}</strong></div></div></> : <div className="chart-empty">Train the model to generate a threshold cost curve.</div>}</div>;
}

const CSV_COLUMNS = ["customer_age_days", "previous_orders", "previous_returns", "previous_refunds", "return_ratio", "refund_ratio", "order_value", "days_since_purchase", "account_count", "address_reuse_count", "device_reuse_count", "payment_failures", "claim_type", "product_category", "is_abuse"];

function SettingsPage({ modelInfo, onTrained }) {
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [training, setTraining] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  async function chooseFile(nextFile) {
    setError(""); setResult(null);
    if (!nextFile) return;
    if (!nextFile.name.toLowerCase().endsWith(".csv")) return setError("Choose a .csv file.");
    if (nextFile.size > 10 * 1024 * 1024) return setError("CSV files must be 10 MB or smaller.");
    const firstLine = (await nextFile.slice(0, 4096).text()).split(/\r?\n/)[0].replace(/^\uFEFF/, "");
    const headers = firstLine.split(",").map((value) => value.trim());
    const missing = CSV_COLUMNS.filter((column) => !headers.includes(column));
    if (missing.length) return setError(`Missing columns: ${missing.join(", ")}`);
    setFile(nextFile);
  }

  async function train() {
    if (!file) return;
    setTraining(true); setError(""); setResult(null);
    try {
      const response = await fetch(`${API_URL}/model/train`, { method: "POST", headers: { "Content-Type": "text/csv", "X-Dataset-Name": file.name }, body: file });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Training failed.");
      setResult(data); onTrained(data);
    } catch (trainingError) { setError(trainingError.message); }
    finally { setTraining(false); }
  }

  function downloadTemplate() {
    const sample = [CSV_COLUMNS.join(","), "365,12,1,0,0.0833,0,2499,10,1,1,1,0,changed_mind,electronics,0", "30,2,2,1,1,0.5,8999,2,3,4,5,2,missing_item,electronics,1"].join("\n");
    const url = URL.createObjectURL(new Blob([sample], { type: "text/csv" }));
    const link = document.createElement("a"); link.href = url; link.download = "risk-training-template.csv"; link.click(); URL.revokeObjectURL(url);
  }

  return <section className="settings-layout">
    <div className="settings-intro"><p className="eyebrow">CUSTOM MODEL</p><h3>Train on your business data</h3><p>Upload labeled historical return cases. We validate the file, reserve 20% for evaluation, train a new XGBoost pipeline, and activate it only after training succeeds.</p></div>
    <div className="settings-grid">
      <div className="settings-card">
        <div className="step-heading"><span>01</span><div><h3>Prepare your CSV</h3><p>One row per completed return case. Include all 15 columns exactly as named.</p></div></div>
        <div className="data-rules"><div><strong>20+ rows</strong><span>More diverse history improves results</span></div><div><strong>0 or 1 label</strong><span>0 = legitimate, 1 = confirmed abuse</span></div><div><strong>No blanks</strong><span>Every field is required</span></div><div><strong>Exact ratios</strong><span>Returns ÷ orders and refunds ÷ orders</span></div></div>
        <button className="secondary-button" onClick={downloadTemplate}>↓ Download CSV template</button>
      </div>
      <div className="settings-card">
        <div className="step-heading"><span>02</span><div><h3>Upload and train</h3><p>The active model is replaced only after validation and training finish.</p></div></div>
        <div className={`drop-zone ${dragging ? "dragging" : ""}`} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); chooseFile(event.dataTransfer.files[0]); }}>
          <div className="upload-icon">⇧</div><strong>{file ? file.name : "Drop your CSV here"}</strong><p>{file ? `${(file.size / 1024).toFixed(1)} KB · ready to train` : "or choose a file from your computer · max 10 MB"}</p><label className="secondary-button">Choose CSV<input type="file" accept=".csv,text/csv" onChange={(event) => chooseFile(event.target.files[0])} /></label>
        </div>
        {error && <div className="form-message error"><strong>Could not use this dataset</strong><span>{error}</span></div>}
        {result && <div className="training-result"><div><span>MODEL ACTIVE</span><strong>{result.rows} rows processed</strong></div><div className="result-metrics"><Metric label="ROC-AUC" value={result.metrics.roc_auc} /><Metric label="Precision" value={result.metrics.precision} percent /><Metric label="Recall" value={result.metrics.recall} percent /><Metric label="F1" value={result.metrics.f1} percent /></div><small>{result.training_rows} training rows · {result.test_rows} evaluation rows</small></div>}
        <button className="primary-button train-button" disabled={!file || training} onClick={train}>{training ? "Training model…" : "Train & activate model"}</button>
      </div>
    </div>
    {modelInfo?.cost_analysis && <CostSettingsCard key={`${modelInfo.cost_analysis.false_positive_unit_cost}-${modelInfo.cost_analysis.false_negative_unit_cost}`} modelInfo={modelInfo} onUpdated={onTrained} />}
    <div className="schema-card"><div><p className="eyebrow">REQUIRED SCHEMA</p><h3>Column reference</h3></div><div className="schema-list">{CSV_COLUMNS.map((column) => <code key={column}>{column}</code>)}</div><p><strong>Category examples:</strong> claim_type can be damaged, missing_item, wrong_item, or changed_mind. product_category can use your own consistent category names.</p></div>
  </section>;
}

function CostSettingsCard({ modelInfo, onUpdated }) {
  const [falsePositiveCost, setFalsePositiveCost] = useState(modelInfo.cost_analysis.false_positive_unit_cost);
  const [falseNegativeCost, setFalseNegativeCost] = useState(modelInfo.cost_analysis.false_negative_unit_cost);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  async function saveCosts() {
    setSaving(true); setError("");
    try {
      const response = await fetch(`${API_URL}/model/cost-settings`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ false_positive_cost: Number(falsePositiveCost), false_negative_cost: Number(falseNegativeCost) }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not update costs.");
      onUpdated(data.model);
    } catch (costError) { setError(costError.message); }
    finally { setSaving(false); }
  }
  return <div className="settings-card cost-settings-card"><div className="step-heading"><span>03</span><div><h3>Merchant loss assumptions</h3><p>Changing these values immediately recalculates the lowest-cost review threshold from held-out results.</p></div></div><div className="cost-inputs"><label><span>False-positive cost (₹)</span><input type="number" min="0" value={falsePositiveCost} onChange={(event) => setFalsePositiveCost(event.target.value)} /><small>Review labour, delay and customer friction.</small></label><label><span>False-negative cost (₹)</span><input type="number" min="0" value={falseNegativeCost} onChange={(event) => setFalseNegativeCost(event.target.value)} /><small>Expected loss when abuse is missed.</small></label></div>{error && <div className="form-message error"><span>{error}</span></div>}<button className="primary-button" disabled={saving} onClick={saveCosts}>{saving ? "Recalculating…" : "Save costs & recalculate"}</button></div>;
}

function Metric({ label, value, percent }) { return <div><span>{label}</span><strong>{percent ? `${(value * 100).toFixed(1)}%` : value.toFixed(4)}</strong></div>; }

const LOW_RISK_SAMPLE = { customer_age_days: 700, previous_orders: 15, previous_returns: 1, previous_refunds: 0, return_ratio: 0.067, refund_ratio: 0, order_value: 1800, days_since_purchase: 12, account_count: 1, address_reuse_count: 1, device_reuse_count: 1, payment_failures: 0, claim_type: "changed_mind", product_category: "grocery" };
const HIGH_RISK_SAMPLE = { customer_age_days: 30, previous_orders: 4, previous_returns: 3, previous_refunds: 2, return_ratio: 0.75, refund_ratio: 0.5, order_value: 8500, days_since_purchase: 3, account_count: 3, address_reuse_count: 4, device_reuse_count: 5, payment_failures: 2, claim_type: "missing_item", product_category: "electronics" };
const NUMBER_FIELDS = [["customer_age_days", "Customer age (days)"], ["previous_orders", "Previous orders"], ["previous_returns", "Previous returns"], ["previous_refunds", "Previous refunds"], ["return_ratio", "Return ratio (0–1)"], ["refund_ratio", "Refund ratio (0–1)"], ["order_value", "Order value (₹)"], ["days_since_purchase", "Days since purchase"], ["account_count", "Linked accounts"], ["address_reuse_count", "Address reuse"], ["device_reuse_count", "Device reuse"], ["payment_failures", "Payment failures"]];

function TestCasePanel({ onClose, onCreated }) {
  const [form, setForm] = useState(LOW_RISK_SAMPLE);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  function update(name, value) {
    setForm((current) => {
      const next = { ...current, [name]: value };
      if (["previous_orders", "previous_returns", "previous_refunds"].includes(name)) {
        const orders = Math.max(1, Number(next.previous_orders));
        next.return_ratio = Number(next.previous_returns) / orders;
        next.refund_ratio = Number(next.previous_refunds) / orders;
      }
      return next;
    });
  }
  async function submit(event) {
    event.preventDefault(); setSubmitting(true); setError("");
    const payload = Object.fromEntries(Object.entries(form).map(([key, value]) => NUMBER_FIELDS.some(([name]) => name === key) ? [key, Number(value)] : [key, value]));
    try { const response = await fetch(`${API_URL}/cases`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); const data = await response.json(); if (!response.ok) throw new Error(data.detail?.[0]?.msg || data.detail || "Could not score case."); await onCreated(data.case.id); }
    catch (submitError) { setError(submitError.message); } finally { setSubmitting(false); }
  }
  return <div className="panel-overlay"><div className="case-panel test-panel"><div className="panel-header"><div><p className="eyebrow">ACTIVE MODEL</p><h2>Test a risk case</h2></div><button className="close-button" onClick={onClose}>×</button></div><div className="sample-switch"><span>Quick sample</span><button onClick={() => setForm(LOW_RISK_SAMPLE)}>Low risk</button><button onClick={() => setForm(HIGH_RISK_SAMPLE)}>High risk</button></div><form onSubmit={submit}><div className="test-form-grid">{NUMBER_FIELDS.map(([name, label]) => <label key={name}><span>{label}</span><input required readOnly={name.includes("ratio")} min={["previous_orders", "account_count"].includes(name) ? "1" : "0"} max={name.includes("ratio") ? "1" : undefined} step={name.includes("ratio") || name === "order_value" ? "0.001" : "1"} type="number" value={form[name]} onChange={(event) => update(name, event.target.value)} /></label>)}<label><span>Claim type</span><select value={form.claim_type} onChange={(event) => update("claim_type", event.target.value)}><option value="changed_mind">Changed mind</option><option value="damaged">Damaged</option><option value="missing_item">Missing item</option><option value="wrong_item">Wrong item</option></select></label><label><span>Product category</span><input required value={form.product_category} onChange={(event) => update("product_category", event.target.value)} /></label></div>{error && <div className="form-message error"><strong>Case could not be tested</strong><span>{error}</span></div>}<div className="form-footer"><button type="button" className="secondary-button" onClick={onClose}>Cancel</button><button className="primary-button" disabled={submitting}>{submitting ? "Scoring case…" : "Run risk test →"}</button></div></form></div></div>;
}


function StatCard({
  title,
  value,
  subtitle,
  type
}) {
  return (
    <div className={`stat-card ${type}`}>

      <div className="stat-top">
        <span>{title}</span>

        <div className="stat-icon">
          {type === "high"
            ? "!"
            : type === "medium"
            ? "◐"
            : type === "low"
            ? "✓"
            : "Σ"}
        </div>
      </div>

      <strong className="stat-value">
        {value}
      </strong>

      <small>{subtitle}</small>

    </div>
  );
}


function RiskBadge({ level }) {
  return (
    <span
      className={`risk-badge ${level?.toLowerCase()}`}
    >
      <span className="badge-dot"></span>
      {level}
    </span>
  );
}


function CasePanel({
  caseId,
  onClose,
  onCaseUpdated
}) {
  const [caseData, setCaseData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [investigating, setInvestigating] = useState(false);
  const [investigation, setInvestigation] = useState(null);
  const [investigationError, setInvestigationError] = useState(null);
  const [decisionSaving, setDecisionSaving] = useState(false);
  const [decisionError, setDecisionError] = useState("");
  const [explanation, setExplanation] = useState([]);
  const [review, setReview] = useState({ evidence: [], events: [] });
  const [evidenceUploading, setEvidenceUploading] = useState(false);
  const [reviewError, setReviewError] = useState("");
  const [outcome, setOutcome] = useState("CONFIRMED_LEGITIMATE");
  const [outcomeNote, setOutcomeNote] = useState("");

  const refreshReview = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/cases/${caseId}/review`);
      const data = await response.json();
      if (response.ok) setReview(data);
    } catch (error) { console.error(error); }
  }, [caseId]);

  useEffect(() => {
    fetch(`${API_URL}/cases/${caseId}`)
      .then((response) => {
        if (!response.ok) throw new Error('Failed to load case');
        return response.json();
      })
      .then((data) => setCaseData(data.case))
      .catch((error) => console.error(error))
      .finally(() => setLoading(false));
    fetch(`${API_URL}/cases/${caseId}/explanation`).then((response) => response.ok ? response.json() : null).then((data) => data && setExplanation(data.explanation || [])).catch(console.error);
    fetch(`${API_URL}/cases/${caseId}/review`).then((response) => response.ok ? response.json() : null).then((data) => data && setReview(data)).catch(console.error);
  }, [caseId]);

  async function runInvestigation() {
    setInvestigating(true);
    setInvestigation(null);
    setInvestigationError(null);

    try {
      const response = await fetch(`${API_URL}/cases/${caseId}/investigate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'AI investigation failed');
      }

      setInvestigation(data.investigation);
    } catch (error) {
      console.error('Investigation error:', error);
      setInvestigationError(error.message);
    } finally {
      setInvestigating(false);
    }
  }

  async function saveDecision(decision) {
    setDecisionSaving(true);
    setDecisionError("");
    try {
      const response = await fetch(`${API_URL}/cases/${caseId}/decision`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not save decision.");
      setCaseData((current) => ({ ...current, merchant_decision: data.merchant_decision }));
      await onCaseUpdated();
      await refreshReview();
    } catch (error) {
      setDecisionError(error.message);
    } finally {
      setDecisionSaving(false);
    }
  }

  async function uploadEvidence(file) {
    if (!file) return;
    setEvidenceUploading(true); setReviewError("");
    try {
      const response = await fetch(`${API_URL}/cases/${caseId}/evidence`, { method: "POST", headers: { "Content-Type": file.type, "X-Filename": file.name }, body: file });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Evidence upload failed.");
      await refreshReview();
    } catch (error) { setReviewError(error.message); }
    finally { setEvidenceUploading(false); }
  }

  async function saveOutcome() {
    setReviewError("");
    try {
      const response = await fetch(`${API_URL}/cases/${caseId}/outcome`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ outcome, note: outcomeNote || null }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not save outcome.");
      setOutcomeNote("");
      await refreshReview();
      await onCaseUpdated();
    } catch (error) { setReviewError(error.message); }
  }

  return (
    <div className="panel-overlay">
      <div className="case-panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">CASE #{String(caseId).padStart(4, '0')}</p>
            <h2>Risk Investigation</h2>
          </div>
          <button className="close-button" onClick={onClose}>×</button>
        </div>

        {loading ? (
          <div className="empty-state">Loading case...</div>
        ) : caseData ? (
          <>
            <div className="risk-summary">
              <div>
                <span>Risk Score</span>
                <strong>{Number(caseData.risk_score).toFixed(1)}%</strong>
              </div>
              <RiskBadge level={caseData.risk_level} />
            </div>

            <div className="detail-section">
              <p className="eyebrow">MODEL SIGNALS</p>
              <div className="detail-grid">
                <Detail label="Return Ratio" value={`${(Number(caseData.return_ratio) * 100).toFixed(1)}%`} />
                <Detail label="Refund Ratio" value={`${(Number(caseData.refund_ratio) * 100).toFixed(1)}%`} />
                <Detail label="Account Reuse" value={caseData.account_count} />
                <Detail label="Address Reuse" value={caseData.address_reuse_count} />
                <Detail label="Device Reuse" value={caseData.device_reuse_count} />
                <Detail label="Payment Failures" value={caseData.payment_failures} />
                <Detail label="Previous Returns" value={caseData.previous_returns} />
                <Detail label="Previous Refunds" value={caseData.previous_refunds} />
              </div>
            </div>

            {explanation.length > 0 && <div className="detail-section"><div className="explain-heading"><div><p className="eyebrow">MODEL EXPLANATION</p><h3>Feature contributions</h3></div><span>LOG-ODDS IMPACT</span></div><div className="contribution-list">{explanation.map((item) => <div key={item.feature} className={item.direction === "increases_risk" ? "risk-up" : "risk-down"}><span>{formatClaim(item.feature)}</span><div className="contribution-track"><i style={{ width: `${Math.min(100, Math.abs(item.contribution) * 35)}%` }}></i></div><strong>{item.contribution > 0 ? "+" : ""}{item.contribution.toFixed(3)}</strong></div>)}</div><small className="explanation-note">Model-native XGBoost contributions. Positive values increase predicted risk; negative values reduce it.</small></div>}

            <div className="detail-section">
              <p className="eyebrow">REQUEST</p>
              <div className="request-info">
                <div><span>Claim</span><strong>{formatClaim(caseData.claim_type)}</strong></div>
                <div><span>Category</span><strong>{formatClaim(caseData.product_category)}</strong></div>
                <div><span>Order Value</span><strong>₹{Number(caseData.order_value).toLocaleString()}</strong></div>
              </div>
            </div>

            <div className="recommended-action">
              <span>Recommended Action</span>
              <strong>{formatAction(caseData.recommended_action)}</strong>
            </div>

            <div className="merchant-decision">
              <div><p className="eyebrow">MERCHANT DECISION</p><h3>{caseData.merchant_decision ? formatAction(caseData.merchant_decision) : "Awaiting review"}</h3><span>Record the final human decision independently from the model recommendation.</span></div>
              <div className="decision-actions"><button disabled={decisionSaving} className={caseData.merchant_decision === "APPROVED" ? "selected approve" : "approve"} onClick={() => saveDecision("APPROVED")}>✓ Approve</button><button disabled={decisionSaving} className={caseData.merchant_decision === "REJECTED" ? "selected reject" : "reject"} onClick={() => saveDecision("REJECTED")}>× Reject</button><button disabled={decisionSaving} className={caseData.merchant_decision === "ESCALATED" ? "selected escalate" : "escalate"} onClick={() => saveDecision("ESCALATED")}>↑ Escalate</button></div>
              {decisionError && <div className="form-message error"><span>{decisionError}</span></div>}
            </div>

            <div className="evidence-review"><div className="review-section-heading"><div><p className="eyebrow">EVIDENCE VERIFICATION</p><h3>Case evidence</h3></div><label className={`secondary-button ${evidenceUploading ? "disabled" : ""}`}>{evidenceUploading ? "Uploading…" : "＋ Add evidence"}<input type="file" accept=".pdf,image/jpeg,image/png,image/webp" disabled={evidenceUploading} onChange={(event) => uploadEvidence(event.target.files[0])} /></label></div><p>Attach delivery proof, invoices, product photos or courier scans. Files are recorded in the audit trail.</p>{review.evidence.length === 0 ? <div className="review-empty">No evidence uploaded yet.</div> : <div className="evidence-list">{review.evidence.map((item) => <a key={item.id} href={`${API_URL}${item.download_url}`} target="_blank" rel="noreferrer"><span>▤</span><div><strong>{item.filename}</strong><small>{(item.size_bytes / 1024).toFixed(1)} KB · {formatDate(item.created_at)}</small></div><b>Open ↗</b></a>)}</div>}<div className="outcome-form"><p className="eyebrow">VERIFIED OUTCOME</p><div><select value={outcome} onChange={(event) => setOutcome(event.target.value)}><option value="CONFIRMED_LEGITIMATE">Confirmed legitimate</option><option value="CONFIRMED_ABUSE">Confirmed abuse</option><option value="CHARGEBACK_RECEIVED">Chargeback received</option><option value="EVIDENCE_ACCEPTED">Evidence accepted</option><option value="DECISION_REVERSED">Decision reversed</option></select><input placeholder="Optional reviewer note" value={outcomeNote} onChange={(event) => setOutcomeNote(event.target.value)} /><button className="primary-button" onClick={saveOutcome}>Record</button></div></div>{reviewError && <div className="form-message error"><span>{reviewError}</span></div>}</div>

            {review.events.length > 0 && <div className="audit-trail"><p className="eyebrow">AUDIT TRAIL</p>{review.events.map((event) => <div key={event.id}><i></i><section><strong>{formatAction(event.value)}</strong><span>{formatClaim(event.event_type)} · {formatDate(event.created_at)}</span>{event.note && <p>{event.note}</p>}</section></div>)}</div>}

            <div className="ai-investigation">
              <div className="ai-header">
                <div className="ai-title">
                  <div className="agent-icon">✦</div>
                  <div>
                    <p className="eyebrow">GEMINI AI</p>
                    <h3>AI Investigation</h3>
                  </div>
                </div>
                <span className="ai-status">AGENT</span>
              </div>

              {!investigation && !investigating && !investigationError && (
                <div className="ai-start">
                  <p>Analyze the case signals and identify the evidence a merchant should verify.</p>
                  <button className="investigate-button" onClick={runInvestigation}>✦ Investigate Case</button>
                </div>
              )}

              {investigating && (
                <div className="ai-loading">
                  <div className="loading-spinner"></div>
                  <div>
                    <strong>AI is investigating...</strong>
                    <p>Analyzing behavioral signals and generating evidence.</p>
                  </div>
                </div>
              )}

              {investigationError && (
                <div className="ai-error">
                  <strong>Investigation unavailable</strong>
                  <p>{investigationError}</p>
                  <button className="retry-button" onClick={runInvestigation}>Try Again</button>
                </div>
              )}

              {investigation && (
                <div className="investigation-result">
                  <div className="investigation-summary">
                    <span>AI SUMMARY</span>
                    <p>{investigation.summary}</p>
                  </div>

                  <div className="investigation-block">
                    <div className="investigation-block-title">
                      <span className="block-number">01</span>
                      <strong>Risk Factors</strong>
                    </div>
                    <ul>
                      {(investigation.risk_factors || []).map((factor, index) => <li key={index}>{factor}</li>)}
                    </ul>
                  </div>

                  <div className="investigation-block">
                    <div className="investigation-block-title">
                      <span className="block-number">02</span>
                      <strong>Evidence to Check</strong>
                    </div>
                    <ul>
                      {(investigation.evidence_to_check || []).map((evidence, index) => <li key={index}>{evidence}</li>)}
                    </ul>
                  </div>

                  <div className="ai-recommendation">
                    <span>AI RECOMMENDATION</span>
                    <strong>{formatAction(investigation.recommended_action)}</strong>
                  </div>

                  <div className="ai-confidence">
                    <div className="confidence-header">
                      <span>AI Confidence</span>
                      <strong>{(Number(investigation.confidence) * 100).toFixed(0)}%</strong>
                    </div>
                    <div className="confidence-bar">
                      <div className="confidence-fill" style={{ width: `${Math.max(0, Math.min(100, Number(investigation.confidence) * 100))}%` }}></div>
                    </div>
                  </div>

                  <button className="rerun-button" onClick={runInvestigation}>↻ Run Investigation Again</button>
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="empty-state">Case not found.</div>
        )}
      </div>
    </div>
  );
}

function Detail({
  label,
  value
}) {
  return (
    <div className="detail">

      <span>{label}</span>

      <strong>{value}</strong>

    </div>
  );
}


function formatClaim(value) {
  if (!value) return "-";

  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) =>
      letter.toUpperCase()
    );
}


function formatAction(value) {
  if (!value) return "-";

  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) =>
      letter.toUpperCase()
    );
}

function formatCurrency(value) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0
  }).format(Number(value || 0));
}

function formatCompactCurrency(value) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    notation: "compact",
    maximumFractionDigits: 1
  }).format(Number(value || 0));
}


function formatDate(value) {
  if (!value) return "";

  return new Date(value).toLocaleString(
    "en-IN",
    {
      dateStyle: "medium",
      timeStyle: "short"
    }
  );
}


export default App;
