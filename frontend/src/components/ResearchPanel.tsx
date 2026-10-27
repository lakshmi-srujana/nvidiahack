import React, { useState } from "react";
import type { TavilyResearchResult } from "../contracts/contracts";
import { MOCK_TAVILY_RESEARCH } from "../services/mockData";
import { Search, ExternalLink, ShieldAlert, Sparkles } from "lucide-react";

export const ResearchPanel: React.FC = () => {
  const [query, setQuery] = useState(MOCK_TAVILY_RESEARCH.query);
  const [data, setData] = useState<TavilyResearchResult>(MOCK_TAVILY_RESEARCH);
  const [isSearching, setIsSearching] = useState(false);

  const handleSearch = () => {
    setIsSearching(true);
    setTimeout(() => {
      setData({
        ...MOCK_TAVILY_RESEARCH,
        query,
        retrieved_at: new Date().toISOString(),
      });
      setIsSearching(false);
    }, 600);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Search Input Box */}
      <div className="glass-panel" style={{ padding: "16px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
          <Sparkles size={18} color="#00e5ff" />
          <h3 style={{ fontSize: "1rem", fontWeight: 700, color: "#f8fafc" }}>
            Situational Intelligence (Tavily Research Adapter)
          </h3>
        </div>

        <p style={{ fontSize: "0.8rem", color: "#94a3b8", marginBottom: "12px" }}>
          Retrieve verified web intelligence, hydrology advisories, and airspace alerts to contextualize mission planning.
        </p>

        <div style={{ display: "flex", gap: "8px" }}>
          <input
            type="text"
            className="mono"
            style={{
              flex: 1,
              background: "rgba(15, 23, 42, 0.8)",
              border: "1px solid rgba(255, 255, 255, 0.15)",
              borderRadius: "8px",
              padding: "10px 14px",
              color: "#f8fafc",
              fontSize: "0.85rem",
              outline: "none",
            }}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search external advisories, weather, or terrain reports..."
          />
          <button
            className="btn btn-primary"
            onClick={handleSearch}
            disabled={isSearching}
          >
            <Search size={16} />
            {isSearching ? "SEARCHING..." : "RETRIEVE"}
          </button>
        </div>
      </div>

      {/* Mandatory Non-Authoritative Disclaimer */}
      <div
        className="glass-panel"
        style={{
          padding: "14px 18px",
          border: "1px solid rgba(245, 158, 11, 0.4)",
          background: "rgba(245, 158, 11, 0.08)",
          display: "flex",
          alignItems: "flex-start",
          gap: "12px",
        }}
      >
        <ShieldAlert size={22} color="#f59e0b" style={{ flexShrink: 0, marginTop: "2px" }} />
        <div>
          <div style={{ fontSize: "0.85rem", fontWeight: 700, color: "#f59e0b" }}>
            SAFETY BOUNDARY: NON-AUTHORITATIVE EXTERNAL DATA
          </div>
          <div style={{ fontSize: "0.75rem", color: "#cbd5e1", marginTop: "4px" }}>
            {data.disclaimer}
          </div>
        </div>
      </div>

      {/* Summary Card */}
      <div className="glass-panel" style={{ padding: "16px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
          <h4 style={{ fontSize: "0.9rem", fontWeight: 700, color: "#00e5ff" }}>
            Synthesized Intelligence Summary
          </h4>
          <span className="badge badge-cyan" style={{ fontSize: "0.65rem" }}>
            {data.is_cached ? "CACHED / OFFLINE SAFE" : "LIVE FEED"}
          </span>
        </div>
        <p style={{ fontSize: "0.85rem", color: "#f8fafc", lineHeight: 1.6 }}>
          {data.summary}
        </p>
      </div>

      {/* Verified Citations List */}
      <div className="glass-panel" style={{ padding: "16px" }}>
        <h4 style={{ fontSize: "0.9rem", fontWeight: 700, color: "#f8fafc", marginBottom: "12px" }}>
          Verified Source Citations ({data.sources.length})
        </h4>

        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {data.sources.map((src, idx) => (
            <div
              key={idx}
              className="glass-panel-elevated"
              style={{ padding: "12px 14px", borderLeft: "3px solid #10b981" }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <a
                  href={src.url}
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    color: "#38bdf8",
                    fontSize: "0.85rem",
                    fontWeight: 600,
                    textDecoration: "none",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                >
                  {src.title}
                  <ExternalLink size={14} />
                </a>
                <span className="mono" style={{ fontSize: "0.75rem", color: "#10b981" }}>
                  Match: {(src.score * 100).toFixed(0)}%
                </span>
              </div>

              <div style={{ fontSize: "0.78rem", color: "#94a3b8", marginTop: "6px" }}>
                "{src.content_snippet}"
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
