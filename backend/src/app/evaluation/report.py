from __future__ import annotations

import json
from pathlib import Path

from app.evaluation.models import EvaluationReport

LABELS = {
    "query_structure": "Estruturação da consulta",
    "startup_recall_at_5": "Recuperação de startups — recall@5",
    "startup_precision_at_5": "Recuperação de startups — precision@5",
    "startup_mrr": "Recuperação de startups — MRR",
    "extraction_fact_recall": "Extração — recall de fatos",
    "forbidden_fact_avoidance": "Extração — ausência de fatos proibidos",
    "classification_accuracy": "Classificação de maturidade",
    "factual_support_accuracy": "Suporte factual",
    "nvidia_recall_at_5": "Recuperação NVIDIA — recall@5",
    "nvidia_precision_at_5": "Recuperação NVIDIA — precision@5",
    "reranking_after_mrr": "Reranking — MRR final",
    "reranking_delta_mrr": "Reranking — delta de MRR",
    "citation_url_validity": "Citações — URLs válidas",
    "citation_recall": "Citações — recall esperado",
    "recommendation_acceptance": "Adequação das recomendações",
    "forbidden_recommendation_avoidance": "Ausência de recomendações proibidas",
    "subjective_rubric": "Rubrica humana",
}


def render_markdown(report: EvaluationReport) -> str:
    lines = [
        "# Relatório resumido de qualidade",
        "",
        f"- Dataset: `{report.dataset_version}`",
        f"- Predições: `{report.prediction_version}`",
        f"- Execução: `{report.run_id}` (`{report.mode}`)",
        f"- Casos avaliados: {report.evaluated_cases}",
        f"- Resultado: **{'APROVADO' if report.passed else 'REPROVADO'}**",
        f"- Rubrica humana: `{report.human_rubric_status}`",
        "",
        "## Métricas",
        "",
        "| Dimensão | Resultado | Mínimo | Status | Casos abaixo do limite |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for metric in report.metrics:
        failed = ", ".join(f"`{case_id}`" for case_id in metric.failed_cases) or "—"
        value = "N/A" if metric.value is None else f"{metric.value:.3f}"
        status = "NÃO EXECUTADA" if metric.passed is None else "OK" if metric.passed else "FALHA"
        lines.append(
            f"| {LABELS[metric.name]} | {value} | {metric.threshold:.3f} | {status} | {failed} |"
        )
    lines.extend(
        [
            "",
            "## Efeito do reranking",
            "",
            "| Ordem | MRR |",
            "| --- | ---: |",
            f"| Antes (híbrida) | {report.reranking_before_mrr:.3f} |",
            f"| Depois (reranker) | {report.reranking_after_mrr:.3f} |",
            f"| Delta | {report.reranking_delta_mrr:+.3f} |",
            "",
            "> O relatório contém apenas métricas e IDs versionados; "
            "respostas brutas não são persistidas.",
            "",
        ]
    )
    return "\n".join(lines)


def write_reports(report: EvaluationReport, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / f"{report.run_id}.md"
    json_path = output_dir / f"{report.run_id}.json"
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    json_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return markdown_path, json_path
