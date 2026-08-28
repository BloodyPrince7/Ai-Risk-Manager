import { signalLabel, timestamp } from "./monitoringApi";

export function SourceFilter({ value, onChange, disabled }) {
  return (
    <label>
      Show requests
      <select aria-label="Show requests" value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)}>
        <option value="all">Customer + test requests</option>
        <option value="live">Customer requests only</option>
        <option value="demo">Test requests only</option>
      </select>
    </label>
  );
}

export function RequestTable({ requests, onView }) {
  if (!requests.length) return <p>No requests to show for this selection.</p>;

  return (
    <div className="table-wrapper">
      <table>
        <thead>
          <tr><th>Request</th><th>Customer / device</th><th>IP address / location</th><th>Received</th><th>Status</th></tr>
        </thead>
        <tbody>
          {requests.map((row) => (
            <tr key={row.id}>
              <td>
                {row.case_id ? <button className="view-button" onClick={() => onView(row.case_id)}>View case #{row.case_id} →</button> : <strong>Request #{row.id}</strong>}
                <small>{row.external_reference || "No order reference"} · {row.is_test ? "TEST" : "CUSTOMER"}</small>
              </td>
              <td><code>{row.account_id || "Customer not provided"}</code><small>{row.device_id || "Device not provided"}</small></td>
              <td><code>{row.ip_address || "IP not provided"}</code><small>{row.location || "Location not provided"}</small></td>
              <td>{timestamp(row.created_at)}</td>
              <td>{row.status === "paused" ? "Blocked while paused" : "Received"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function PatternCards({ patterns, onView }) {
  return (
    <div className="pattern-list">
      {patterns.map((group) => (
        <article className="sentinel-alert pattern-card" key={group.id}>
          <div className="sentinel-alert-title">
            <div>
              <span>{group.is_test ? "TEST REQUESTS" : "CUSTOMER REQUESTS"} · {group.field === "location" ? "LOCATION MATCH" : "MATCH FOUND"}</span>
              <h4>Same {group.field === "ip_address" ? "IP address" : signalLabel(group.field).toLowerCase()}</h4>
            </div>
            <strong>{group.count} requests · {group.account_count} identified accounts</strong>
          </div>
          <p>{group.count} requests have this {group.field === "ip_address" ? "IP address" : signalLabel(group.field).toLowerCase()} in common:</p>
          <code className="pattern-value">{group.value}</code>
          <p className="pattern-time">First request: {timestamp(group.first_seen)} · Most recent: {timestamp(group.last_seen)}</p>
          {group.field === "location" && <p className="sentinel-caution">Many unrelated customers live in the same place. A location match alone is not a reason to block anyone.</p>}
          <details>
            <summary>View the {group.count} requests and what else they share</summary>
            {group.similarities.length > 0 && <div className="sentinel-evidence">
              {group.similarities.map((item) => (
                <div key={item.field + ":" + item.value}>
                  <span>{signalLabel(item.field)} · {item.count} requests</span>
                  <code>{["claim_type", "product_category"].includes(item.field) ? item.value.replaceAll("_", " ") : item.value}</code>
                </div>
              ))}
            </div>}
            <RequestTable requests={group.requests} onView={onView} />
          </details>
        </article>
      ))}
    </div>
  );
}

export function SignalHelp() {
  return (
    <details className="monitor-help">
      <summary>What do these details mean?</summary>
      <dl>
        <div><dt>Customer account</dt><dd>The account that submitted the return request.</dd></div>
        <div><dt>Device</dt><dd>A device identifier provided with the request. Multiple accounts may use the same device.</dd></div>
        <div><dt>IP address</dt><dd>A network address. Customers on shared Wi-Fi may have the same IP.</dd></div>
        <div><dt>City or region</dt><dd>The location provided with the request. We do not look it up from the IP address.</dd></div>
        <div><dt>Payment / address reference</dt><dd>An identifier used to match payment or delivery details, without displaying card numbers or full addresses.</dd></div>
      </dl>
      <p>These details come from submitted requests and are not independently verified. A match is a reason to check, not proof of abuse.</p>
    </details>
  );
}

