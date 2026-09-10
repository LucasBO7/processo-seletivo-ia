import { useState } from "react";

import { AnalysisClientError, analyzeStartups } from "../api/analysis-client";
import type { SearchResponse } from "../api/analysis-types";
import { AnalysisState, LoadingState } from "../components/AnalysisState";
import { SearchForm } from "../components/SearchForm";
import { StartupDetails } from "../components/StartupDetails";
import { StartupList } from "../components/StartupList";

export function HomePage() {
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [loading, setLoading] = useState(false);
  const [networkError, setNetworkError] = useState("");

  async function submit(composedQuery: string) {
    setLoading(true);
    setNetworkError("");
    setResponse(null);
    setSelectedId("");
    try {
      const result = await analyzeStartups(composedQuery);
      setResponse(result);
      setSelectedId(result.candidate_startups[0]?.startup_id ?? "");
    } catch (error) {
      setNetworkError(
        error instanceof AnalysisClientError
          ? error.message
          : "Não foi possível concluir a análise.",
      );
    } finally {
      setLoading(false);
    }
  }

  function useQuestion(question: string) {
    setQuery((current) => `${current.trim()}\n${question}`.trim());
    document.querySelector<HTMLTextAreaElement>("#startup-query")?.focus();
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <nav className="topbar__content" aria-label="Identificação do projeto">
          <span className="brand-mark" aria-hidden="true">
            IA
          </span>
          <div>
            <strong>NVIDIA Startup AI Radar</strong>
            <span>Inteligência de ecossistema</span>
          </div>
          {/* <span className="status-pill"><i aria-hidden="true" /> API integrada</span> */}
        </nav>
      </header>

      <section className="workspace">
        <SearchForm
          query={query}
          loading={loading}
          onQueryChange={setQuery}
          onSubmit={submit}
        />
        {loading && <LoadingState />}
        {!loading && (
          <AnalysisState
            response={response}
            networkError={networkError}
            onUseQuestion={useQuestion}
          />
        )}
        {!loading && response && response.candidate_startups.length > 0 && (
          <div className="results-layout">
            <StartupList
              startups={response.candidate_startups}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
            <StartupDetails response={response} startupId={selectedId} />
          </div>
        )}
      </section>
    </main>
  );
}
