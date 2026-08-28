import { useState } from "react";
import { PatternCards, RequestTable, SignalHelp, SourceFilter } from "./MonitoringCommon";
import { signalLabel, timestamp, useMonitor } from "./monitoringApi";
import "./SentinelPanel.css";

export default function PatternPage({ apiUrl, onView }) {
  const [source, setSource] = useState("all");
  const [signal, setSignal] = useState("all");
  const { data, error, refresh } = useMonitor(apiUrl, `/monitoring/patterns?source=${source}`);
  const patterns = data?.patterns.filter((group) => signal === "all" || group.field === signal) || [];

  return (
    <section className="sentinel content-card" id="pattern-analysis">
      <div className="card-header sentinel-heading">
        <div>
          <p className="eyebrow">REQUEST PATTERNS</p>
          <h3>Are these requests connected?</h3>
          <p>Find requests from the same customer, device, network or location. We check for matches every 5 seconds.</p>
        </div>
      </div>
      <div className="sentinel-body">
        <div className="monitor-guide">
          <strong>You do not need to start a check here.</strong>
          <p>As soon as two requests share a detail, they appear together below. Open a group to see the requests. No one is blocked automatically.</p>
        </div>
        <div className="sentinel-controls">
          <SourceFilter value={source} onChange={setSource} />
          <label>
            Shared detail
            <select aria-label="Shared detail" value={signal} onChange={(event) => setSignal(event.target.value)}>
              <option value="all">All matching details</option>
              {["account_id", "device_id", "ip_address", "location", "payment_token", "address_token"].map((field) => <option key={field} value={field}>{signalLabel(field)}</option>)}
            </select>
          </label>
          <button className="secondary-button" onClick={() => refresh()}>Refresh now</button>
        </div>
        {error && <p className="form-message error" role="alert">Could not update matches. {error} You may be seeing older results.</p>}
        {!data ? <p>Looking for matching requests…</p> : <>
          <div className="sentinel-stats">
            <div><span>Requests checked</span><strong>{data.request_count}</strong><small>All recorded requests in this filter</small></div>
            <div><span>Requests with useful details</span><strong>{data.identified_count}</strong><small>At least one detail we can compare</small></div>
            <div><span>Requests with a match</span><strong>{data.linked_request_count}</strong><small>Share a detail with another request</small></div>
            <div><span>Matching groups</span><strong>{patterns.length}</strong><small>{signal === "all" ? "One group per matching detail" : "Groups for the selected detail"}</small></div>
          </div>
          <p className="sentinel-disclaimer">A match does not prove fraud. Shared Wi-Fi, family devices and common locations can be normal.</p>
          <p className="pattern-time">Last updated {timestamp(data.checked_at)}. A request may appear in several groups. Customer and test requests are never matched to each other.</p>
          {patterns.length ? <PatternCards patterns={patterns} onView={onView} /> : <div className="sentinel-empty">
            <strong>{data.request_count === 0 ? "No requests to compare yet" : "No matching requests found"}</strong>
            <p>{data.request_count === 0 ? "Create a test request from Request Traffic to get started." : "Try another shared detail or wait for more requests. Missing details cannot be compared."}</p>
          </div>}
          <SignalHelp />
          <details className="sentinel-history">
            <summary>Recent requests · showing {data.recent_requests.length}</summary>
            <RequestTable requests={data.recent_requests} onView={onView} />
          </details>
        </>}
      </div>
    </section>
  );
}

