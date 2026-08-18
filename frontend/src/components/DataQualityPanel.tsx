/**
 * Every anomaly found in the extracts, and what the tool did about it.
 *
 * A first-class view rather than a footnote. The treatment column is the point:
 * a figure a trader disputes at 07:30 is only defensible if we can say exactly
 * what was changed underneath it, so nothing here is reported without saying
 * how it was handled.
 */

import { useMemo, useState } from "react";
import type { DataQualityIssue, DataQualityResponse, Severity } from "../api/types";
import { Empty } from "./Loading";

const SEVERITY_ORDER: Severity[] = ["ERROR", "WARNING", "INFO"];

const SEVERITY_HELP: Record<Severity, string> = {
  ERROR: "Would have produced a materially wrong number, or could not be treated",
  WARNING: "Real defect, safely repaired or handled conservatively",
  INFO: "Observed and harmless, recorded so nobody re-investigates it",
};

function badgeStyle(severity: Severity): React.CSSProperties {
  const colour =
    severity === "ERROR" ? "#f2545b" : severity === "WARNING" ? "#e0a33e" : "#6b7c8c";
  return {
    display: "inline-block",
    padding: "1px 7px",
    borderRadius: 4,
    fontSize: 11,
    fontWeight: 600,
    color: colour,
    border: `1px solid ${colour}55`,
    background: `${colour}14`,
    whiteSpace: "nowrap",
  };
}

export function DataQualityPanel({ quality }: { quality: DataQualityResponse }) {
  const [filter, setFilter] = useState<Severity | "ALL">("ALL");

  const issues = useMemo(
    () =>
      filter === "ALL"
        ? quality.issues
        : quality.issues.filter((issue) => issue.severity === filter),
    [quality.issues, filter],
  );

  const byCode = useMemo(() => {
    const counts = new Map<string, number>();
    for (const issue of quality.issues) {
      counts.set(issue.code, (counts.get(issue.code) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [quality.issues]);

  return (
    <div className="panel">
      <h2>Data quality</h2>
      <p className="hint">
        {quality.issues.length} findings across the four extracts as of {quality.as_of}.
        Every one is either repaired with a treatment we can defend, or escalated
        untreated &mdash; but always recorded.
      </p>

      <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
        <button
          type="button"
          onClick={() => setFilter("ALL")}
          style={{
            ...badgeStyle("INFO"),
            cursor: "pointer",
            opacity: filter === "ALL" ? 1 : 0.55,
          }}
        >
          ALL {quality.issues.length}
        </button>
        {SEVERITY_ORDER.map((severity) => (
          <button
            key={severity}
            type="button"
            title={SEVERITY_HELP[severity]}
            onClick={() => setFilter(severity)}
            style={{
              ...badgeStyle(severity),
              cursor: "pointer",
              opacity: filter === severity ? 1 : 0.55,
            }}
          >
            {severity} {quality.counts[severity] ?? 0}
          </button>
        ))}
        <span style={{ marginLeft: "auto", fontSize: 11, color: "#8a97a6" }}>
          {byCode.length} distinct checks fired
        </span>
      </div>

      {issues.length === 0 ? (
        <Empty>Nothing to report at this severity.</Empty>
      ) : (
      <div className="scroll">
        <table>
          <thead>
            <tr>
              <th>Severity</th>
              <th>Check</th>
              <th>Entity</th>
              <th>What was found</th>
              <th>Treatment applied</th>
            </tr>
          </thead>
          <tbody>
            {issues.map((issue: DataQualityIssue, index) => (
              <tr key={`${issue.code}-${issue.entity_id}-${index}`}>
                <td>
                  <span style={badgeStyle(issue.severity)}>{issue.severity}</span>
                </td>
                <td style={{ whiteSpace: "nowrap" }}>{issue.code}</td>
                <td style={{ whiteSpace: "nowrap" }}>{issue.entity_id}</td>
                <td>{issue.detail}</td>
                <td className="flat">{issue.treatment}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      )}
    </div>
  );
}
