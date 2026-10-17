"""Rules bound the classifier's interpretation; neither can confirm disease."""

from . import classifier
from .context import observation_time, vaccination_context
from .features import symptom_set
from .rules import DISEASE_LABELS, evaluate_rules


def assess(report: dict, animal: dict, now):
    now = observation_time(now)
    rules = evaluate_rules(report, animal)
    probabilities, version = classifier.predict(report, animal, now)
    ordered = sorted(rules['strengths'], key=lambda key: rules['strengths'][key], reverse=True)
    strongest, runner_up = ordered[:2]
    strength = rules['strengths'][strongest]
    conflict = strength >= 0.8 and rules['strengths'][runner_up] >= 0.8 and strength - rules['strengths'][runner_up] <= 0.1
    disease = 'undifferentiated'
    if conflict:
        rules['triggered_rules'].append('CONFLICTING_PATTERNS: several strong patterns overlap; examination is required.')
    elif strength >= 0.55:
        if probabilities is None or strength >= 0.85 or probabilities.get(strongest, 0) >= 0.35:
            disease = strongest
    if disease == 'undifferentiated':
        rules['triggered_rules'].append('UNCERTAINTY: insufficient, conflicting or unsupported evidence; no specific diagnosis established.')
    missing = []
    if report.get('temperature_c') is None:
        missing.append('Measured temperature')
    if report.get('vaccination_status', 'unknown') == 'unknown' and vaccination_context(report, animal, disease, now)['status'] == 'unknown':
        missing.append('Disease-specific vaccination record')
    if not symptom_set(report):
        missing.append('Specific observed symptoms or professional examination')
    if 'skin_lesions' in symptom_set(report) and not report.get('image_url'):
        missing.append('Optional lesion photograph or veterinary lesion examination')
    if disease in ('lsd', 'fmd'):
        missing.append('Veterinary examination and laboratory confirmation')
    if conflict:
        missing.append('Professional differentiation of overlapping symptom patterns')
    if probabilities and disease != 'undifferentiated' and probabilities.get(disease, 0) < 0.35:
        missing.append('Classifier/rule disagreement requires veterinary assessment')
    if probabilities is None:
        missing.append('Prototype classifier unavailable; rules-only assessment has no model probability')
    if rules['urgent']:
        escalation = 'Contact a veterinarian immediately; reported mortality or inability to stand needs urgent assessment.'
    elif rules['severity'] == 'high' or disease in ('lsd', 'fmd'):
        escalation = 'Urgent veterinary review recommended; arrange professional assessment and appropriate sampling.'
    else:
        escalation = 'Veterinary review recommended; continue monitoring and report worsening observations.'
    safe_actions = ['Contact your veterinarian and share the observations and animal health record.',
                    'Monitor appetite, activity, temperature if safely measurable, and changes in the herd.',
                    'Maintain hygiene of hands, footwear and animal equipment.']
    if symptom_set(report) or report.get('mortality_count', 0):
        safe_actions.insert(0, 'Separate the affected animal where safe and practical; restrict nonessential animal movement pending veterinary advice.')
    if report.get('mortality_count', 0):
        safe_actions.append('Keep people and other animals away from carcasses and contact veterinary authorities for safe handling instructions.')
    return {
        'suspected_disease': DISEASE_LABELS[disease], 'disease_code': disease,
        'probability': round(probabilities.get(disease, 0), 4) if probabilities is not None else None,
        'probability_kind': 'uncalibrated_synthetic_model_score' if probabilities is not None else 'unavailable_rules_only',
        'severity': rules['severity'], 'triggered_rules': rules['triggered_rules'],
        'rule_strength': round(strength, 4), 'missing_information': missing,
        'recommended_escalation': escalation, 'model_version': version,
        'model_source': classifier.MODEL_SOURCE if probabilities is not None else 'Deterministic rules only; no model probability',
        'safe_actions': safe_actions, 'assessment_notice': 'AI-assisted preliminary assessment. Decision-support only; not a confirmed diagnosis.',
    }
