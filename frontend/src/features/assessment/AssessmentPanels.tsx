import { AlertTriangle, CheckCircle2, ShieldCheck, Stethoscope } from 'lucide-react'
import { Badge, Panel, human } from '../../components/ui'
import type { Risk, Triage } from '../../types'

export function TriagePanel({ triage }: { triage: Triage | null }) {
  if (!triage) return <Panel title="Preliminary assessment"><div className="padded assessment-pending">
    <ShieldCheck size={32}/><div><h3>Report recorded · assessment pending</h3>
      <p>This saved report does not have an automated assessment yet. Veterinary review is recommended.</p></div>
  </div></Panel>

  const disease = /^(possible|suspected)|unknown|unclassified|undifferentiated|insufficient/i.test(triage.suspected_disease)
    ? triage.suspected_disease : `Possible ${triage.suspected_disease}`
  return <Panel title="Preliminary assessment" subtitle="Structured symptoms, animal history and measured observations">
    <div className="padded assessment-content">
      <p className="eyebrow">AI-ASSISTED PRELIMINARY ASSESSMENT</p>
      <h2>{disease}</h2>
      <div className="assessment-summary"><span>Severity</span><Badge value={triage.severity}/></div>
      <div className="escalation-notice"><Stethoscope size={21}/><p>{triage.recommended_escalation}</p></div>
      <div className="confidence-block">
        <span>Synthetic prototype confidence</span>
        <strong>{triage.probability === null ? 'Unavailable' : `${Math.round(triage.probability * 100)}%`}</strong>
        <p>{triage.probability === null ? 'Rules-only assessment. No model confidence is available.' : 'Calculated by a model trained on synthetic examples. This is not a clinically validated disease probability.'}</p>
      </div>
      <details className="method-details"><summary>Assessment method</summary>
        <dl className="detail-list compact-details"><div><dt>Model source</dt><dd>{human(triage.model_source)}</dd></div>
          <div><dt>Model version</dt><dd className="mono">{triage.model_version}</dd></div>
          {triage.probability_kind && <div><dt>Confidence type</dt><dd>{human(triage.probability_kind)}</dd></div>}
        </dl>
        <p className="small muted">The structured rules and risk calculation operate without an LLM. A veterinarian or laboratory establishes the professional conclusion.</p>
      </details>
    </div>
  </Panel>
}

export function RiskPanel({ risk }: { risk: Risk }) {
  const sum = risk.factors.reduce((total, factor) => total + factor.points, 0)
  const consistent = Math.abs(sum - risk.score) < 0.001
  return <Panel guide="risk-panel" title="Explainable risk score" subtitle="Each point comes from a recorded factor">
    <div className={`padded risk-assessment risk-${risk.level.toLowerCase()}`}>
      <div className="risk-total"><strong>{risk.score}<small>/100</small></strong><Badge value={risk.level}/></div>
      <div className="risk-meter" role="meter" aria-label="Risk score" aria-valuemin={0} aria-valuemax={100} aria-valuenow={risk.score} aria-valuetext={`${risk.score} out of 100, ${risk.level}`}><span style={{ width: `${risk.score}%` }}/></div>
      <div className="risk-bands"><span><i className="low"/>Low 0–29</span><span><i className="moderate"/>Moderate 30–59</span><span><i className="high"/>High 60–79</span><span><i className="critical"/>Critical 80–100</span></div>
      <div className="risk-factor-list">{risk.factors.map(factor => <div className="risk-factor" key={factor.key}>
        <span><strong>{factor.label}</strong><small>{factor.detail}</small></span><b>{factor.points >= 0 ? '+' : ''}{factor.points}</b>
      </div>)}</div>
      <div className={`factor-total ${consistent ? '' : 'factor-mismatch'}`}>
        {consistent ? <CheckCircle2 size={17}/> : <AlertTriangle size={17}/>}
        <span>Factor total</span><strong>{Number(sum.toFixed(2))} / 100</strong>
      </div>
      {!consistent && <p role="alert" className="small">The stored score and factors do not agree. Ask the care team to review this assessment.</p>}
      <p className="small muted risk-footnote">This score prioritizes review; it does not confirm a disease.</p>
    </div>
  </Panel>
}

export function ReasoningPanel({ triage }: { triage: Triage }) {
  return <Panel title="Why this assessment?" subtitle="Rules triggered by this report, with information still needed">
    <div className="padded reasoning-content"><h3>Triggered rules</h3>
      {triage.triggered_rules.length ? <ul className="plain-list">{triage.triggered_rules.map((rule, index) => <li key={index}>{rule}</li>)}</ul> : <p>No disease-specific rule matched this report.</p>}
      <h3>Missing information</h3>
      {triage.missing_information.length ? <ul className="plain-list">{triage.missing_information.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p>No additional information was flagged by the engine.</p>}
      <p className="small muted">Complete observations improve review. Missing information is never treated as confirmation.</p>
    </div>
  </Panel>
}

export function SafeActionsPanel({ actions }: { actions: string[] }) {
  if (!actions.length) return null
  return <Panel title="While you arrange veterinary review" subtitle="Safe immediate actions">
    <ul className="safe-actions padded">{actions.map((action, index) => <li key={index}><ShieldCheck size={18}/><span>{action}</span></li>)}</ul>
  </Panel>
}
