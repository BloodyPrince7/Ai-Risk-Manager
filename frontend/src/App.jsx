import { useEffect, useState } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

function App() {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCase, setSelectedCase] = useState(null);

  useEffect(() => {
    fetchCases();
  }, []);

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

  const highRisk = cases.filter(
    (item) => item.risk_level === "HIGH"
  ).length;

  const mediumRisk = cases.filter(
    (item) => item.risk_level === "MEDIUM"
  ).length;

  const lowRisk = cases.filter(
    (item) => item.risk_level === "LOW"
  ).length;

  return (
    <div className="app">

      {/* Sidebar */}

      <aside className="sidebar">

        <div className="brand">
          <div className="brand-icon">◆</div>

          <div>
            <h1>Risk Manager</h1>
            <span>AI Commerce Security</span>
          </div>
        </div>

        <nav>

          <button className="nav-item active">
            <span>▦</span>
            Overview
          </button>

          <button className="nav-item">
            <span>◉</span>
            Risk Cases
          </button>

          <button className="nav-item">
            <span>⌁</span>
            Investigations
          </button>

          <button className="nav-item">
            <span>⚙</span>
            Settings
          </button>

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


      {/* Main */}

      <main className="main">

        <header className="topbar">

          <div>
            <p className="eyebrow">MERCHANT CONSOLE</p>
            <h2>Risk Overview</h2>
          </div>

          <div className="topbar-right">

            <div className="model-status">
              <span className="pulse"></span>
              AI Model Active
            </div>

            <div className="avatar">
              PM
            </div>

          </div>

        </header>


        {/* Stats */}

        <section className="stats-grid">

          <StatCard
            title="Total Cases"
            value={cases.length}
            subtitle="All return requests"
            type="neutral"
          />

          <StatCard
            title="High Risk"
            value={highRisk}
            subtitle="Requires attention"
            type="high"
          />

          <StatCard
            title="Medium Risk"
            value={mediumRisk}
            subtitle="Evidence recommended"
            type="medium"
          />

          <StatCard
            title="Low Risk"
            value={lowRisk}
            subtitle="Auto-approvable"
            type="low"
          />

        </section>


        {/* Cases */}

        <section className="content-card">

          <div className="card-header">

            <div>
              <p className="eyebrow">LIVE QUEUE</p>
              <h3>Recent Risk Cases</h3>
            </div>

            <button
              className="refresh-button"
              onClick={fetchCases}
            >
              ↻ Refresh
            </button>

          </div>


          {loading ? (

            <div className="empty-state">
              Loading risk cases...
            </div>

          ) : cases.length === 0 ? (

            <div className="empty-state">

              <div className="empty-icon">◌</div>

              <h3>No cases yet</h3>

              <p>
                Create a return-risk case through the API
                to see it here.
              </p>

            </div>

          ) : (

            <div className="table-wrapper">

              <table>

                <thead>

                  <tr>
                    <th>CASE</th>
                    <th>RISK SCORE</th>
                    <th>LEVEL</th>
                    <th>CLAIM</th>
                    <th>ORDER VALUE</th>
                    <th>ACTION</th>
                    <th></th>
                  </tr>

                </thead>

                <tbody>

                  {cases.map((item) => (

                    <tr key={item.id}>

                      <td>
                        <strong>
                          #{String(item.id).padStart(4, "0")}
                        </strong>

                        <small>
                          {formatDate(item.created_at)}
                        </small>
                      </td>

                      <td>
                        <strong className="score">
                          {Number(item.risk_score).toFixed(1)}%
                        </strong>
                      </td>

                      <td>
                        <RiskBadge
                          level={item.risk_level}
                        />
                      </td>

                      <td>
                        {formatClaim(item.claim_type)}
                      </td>

                      <td>
                        ₹{Number(item.order_value).toLocaleString()}
                      </td>

                      <td>
                        <span className="action-text">
                          {formatAction(item.recommended_action)}
                        </span>
                      </td>

                      <td>
                        <button
                          className="view-button"
                          onClick={() =>
                            setSelectedCase(item.id)
                          }
                        >
                          View →
                        </button>
                      </td>

                    </tr>

                  ))}

                </tbody>

              </table>

            </div>

          )}

        </section>


        {/* Bottom information */}

        <section className="bottom-grid">

          <div className="info-card">

            <p className="eyebrow">MODEL</p>

            <h3>XGBoost Risk Engine</h3>

            <p>
              The model evaluates customer behavior,
              return history, reuse signals and
              transaction attributes.
            </p>

            <div className="model-metrics">

              <div>
                <span>ROC-AUC</span>
                <strong>0.7731</strong>
              </div>

              <div>
                <span>Precision</span>
                <strong>75.0%</strong>
              </div>

              <div>
                <span>Recall</span>
                <strong>49.8%</strong>
              </div>

            </div>

          </div>


          <div className="info-card">

            <p className="eyebrow">DECISION ENGINE</p>

            <h3>Risk-based routing</h3>

            <div className="routing-row">
              <RiskBadge level="LOW" />
              <span>&lt; 20%</span>
              <strong>Auto Approve</strong>
            </div>

            <div className="routing-row">
              <RiskBadge level="MEDIUM" />
              <span>20–60%</span>
              <strong>Request Evidence</strong>
            </div>

            <div className="routing-row">
              <RiskBadge level="HIGH" />
              <span>≥ 60%</span>
              <strong>Manual Review</strong>
            </div>

          </div>

        </section>

      </main>


      {/* Case panel */}

      {selectedCase && (

        <CasePanel
          caseId={selectedCase}
          onClose={() => setSelectedCase(null)}
        />

      )}

    </div>
  );
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
  onClose
}) {
  const [caseData, setCaseData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [investigating, setInvestigating] = useState(false);
  const [investigation, setInvestigation] = useState(null);
  const [investigationError, setInvestigationError] = useState(null);

  useEffect(() => {
    setCaseData(null);
    setInvestigation(null);
    setInvestigationError(null);
    setLoading(true);

    fetch(`${API_URL}/cases/${caseId}`)
      .then((response) => {
        if (!response.ok) throw new Error('Failed to load case');
        return response.json();
      })
      .then((data) => setCaseData(data.case))
      .catch((error) => console.error(error))
      .finally(() => setLoading(false));
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