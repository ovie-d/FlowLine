"use client";

import { useQuery } from "@tanstack/react-query";
import { getModelInfo } from "@/lib/forecastApi";
import type { CiTriple, RegionSummary } from "@/lib/forecastTypes";
import { PanelMessage } from "./ForecastPanel";
import { Modal } from "./Modal";

const ci = ([p, lo, hi]: CiTriple, d = 3) => `${p.toFixed(d)} (${lo.toFixed(d)} to ${hi.toFixed(d)})`;

function Region({ name, r, plain }: { name: string; r: RegionSummary; plain: string }) {
  return (
    <section className="rounded-lg border border-border p-3">
      <h3 className="font-semibold text-fg">{name} · {r.n_test} held-out incidents</h3>
      <p className="mt-1 text-fg">{plain}</p>
      <table className="mt-2 w-full text-left text-[12px]">
        <thead className="text-muted">
          <tr><th className="font-normal">Metric (95% CI)</th><th className="font-normal">Flowline model</th>
            <th className="font-normal">Best simple baseline</th></tr>
        </thead>
        <tbody className="whitespace-nowrap font-mono text-[11px]">
          <tr><td className="whitespace-normal pr-2 font-sans text-muted">Log loss (lower is better)</td><td>{ci(r.model.log_loss)}</td><td>{ci(r.best_baseline.log_loss)}</td></tr>
          <tr><td className="whitespace-normal pr-2 font-sans text-muted">Top-1 correct</td><td>{ci(r.model.top1, 2)}</td><td>{ci(r.best_baseline.top1, 2)}</td></tr>
          <tr><td className="whitespace-normal pr-2 font-sans text-muted">Top-3 contains the actual hazard</td><td>{ci(r.model.top3, 2)}</td><td>{ci(r.best_baseline.top3, 2)}</td></tr>
        </tbody>
      </table>
      <p className="mt-1 text-[11px] text-muted">Baseline: {r.best_baseline.name.replace("Baseline: ", "")}.</p>
    </section>
  );
}

export function AboutModelModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const q = useQuery({ queryKey: ["model-info"], queryFn: getModelInfo, enabled: open, staleTime: Infinity });
  const m = q.data;
  return (
    <Modal open={open} onClose={onClose} title="About this model" wide>
      {q.error ? <PanelMessage tone="error" text={(q.error as Error).message} /> : !m ? (
        <div className="h-64 animate-pulse rounded bg-panel-2" aria-busy aria-label="Loading model information" />
      ) : (
        <div className="grid gap-3 text-[13px]">
          <p className="text-muted">
            Trained on national CER incidents ({m.split.train}); tested on {m.split.test} it never saw.
            Deployed model trained through {m.deployed_model.trained_through} on {m.deployed_model.n_train} incidents.
          </p>
          <div className="grid gap-3 md:grid-cols-2">
            <Region name="Canada" r={m.canada} plain={m.plain_words.canada} />
            <Region name="Alberta" r={m.alberta} plain={m.plain_words.alberta} />
          </div>
          <section className="rounded-lg border border-border p-3 text-[12px]">
            <h3 className="font-semibold text-fg">Year by year (trained only on earlier years)</h3>
            <table className="mt-1 w-full text-left font-mono">
              <thead className="font-sans text-muted"><tr><th className="font-normal">Year</th><th className="font-normal">n</th>
                <th className="font-normal">Model log loss</th><th className="font-normal">National base rate</th></tr></thead>
              <tbody>{m.rolling_origin.map((r) => (
                <tr key={r.year}><td>{r.year}</td><td>{r.n}</td><td>{r.model_log_loss.toFixed(3)}</td>
                  <td>{r.national_base_log_loss.toFixed(3)}</td></tr>))}</tbody>
            </table>
          </section>
          <ul className="list-disc pl-5 text-[12px] text-muted">
            <li>{m.plain_words.weather}</li>
            <li>
              {m.plain_words.calibration} ({m.calibration_above_threshold.n_forecasts_above} held-out forecasts were
              above 50%; observed rate {m.calibration_above_threshold.observed_rate ?? "—"}.)
            </li>
            <li>Low evidence base: {m.low_evidence_rule}.</li>
          </ul>
          <p className="text-[12px] text-muted">{m.disclaimer} Full report: docs/MODEL_REPORT.md.</p>
        </div>
      )}
    </Modal>
  );
}
