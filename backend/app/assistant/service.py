import json
import re
from pathlib import Path
import httpx

from app.assistant.provider import GeminiIntentProvider, sanitized_text
from app.assistant.schemas import GuidanceResponse
from app.auth import authorized_document
from app.triage.rules import evaluate_rules

CATALOG = json.loads((Path(__file__).parent / 'catalog.json').read_text(encoding='utf-8'))


def respond(payload, user, db, settings):
    from fastapi import HTTPException
    context = payload.context
    if context:
        for target in context.targets:
            entry = CATALOG['targets'].get(target)
            if not entry or user['role'] not in entry['roles'] or ('*' not in entry['pages'] and context.page not in entry['pages']):
                raise HTTPException(422, 'Unregistered or unauthorized page target')
        if context.case_id and context.page != 'case_detail':
            raise HTTPException(422, 'Case context requires the case-detail page')
    text = payload.text.lower()
    result = GuidanceResponse()
    for entry in CATALOG['intents']:
        if re.search(entry['pattern'], text, re.IGNORECASE):
            result.intent = entry['id']
            break
    # Optional provider is only used when deterministic help did not recognize the question.
    if result.intent == 'unknown' and payload.external_consent and settings.gemini_api_key.get_secret_value() and settings.gemini_model:
        try:
            result.intent = GeminiIntentProvider(settings).classify(sanitized_text(payload.text)).intent
            result.source = 'gemini'
        except (ValueError, KeyError, IndexError, TypeError, httpx.HTTPError):
            result.source = 'fallback'
    if result.intent == 'unknown':
        return result
    target = next(e['target'] for e in CATALOG['intents'] if e['id'] == result.intent)
    if user['role'] not in CATALOG['targets'][target]['roles']:
        result.message_key = 'denied'
        return result
    if not context:
        result.message_key = 'consent'
        return result
    result.target = target
    result.message_key = 'point'
    if result.intent == 'track':
        if context.page == 'case_detail' and context.case_id:
            case = authorized_document(db, 'disease_cases', context.case_id, user)
            result.case_status = case['status'] if case['status'] in CATALOG['statuses'] else None
            result.target = 'case-status'
        else:
            result.message_key = 'statusMissing'
    return result


def concern(payload, user, db):
    animal = authorized_document(db, 'animals', payload.animal_id, user)
    observations = payload.observations.model_dump(exclude_none=True)
    known = observations.pop('symptoms')
    observations['symptoms'] = [key for key, value in known.items() if value is True]
    # No complete ReportInput is fabricated. Unknown fields are absent and no RF/risk
    # probability is calculated from incomplete conversational observations.
    rules = evaluate_rules(observations, animal)
    active = bool(observations['symptoms']) or any(k in observations for k in ('appetite', 'activity', 'temperature_c', 'mortality_count'))
    urgency = 'urgent' if rules['severity'] in ('high', 'critical') else 'attention' if active and rules['severity'] == 'moderate' else 'insufficient'
    missing = [key for key in ('appetite', 'activity', 'temperature_c', 'duration_hours', 'mortality_count') if key not in observations]
    missing += [s['key'] for s in CATALOG['symptoms'] if known.get(s['key']) is None]
    return {'message_key': urgency, 'severity': rules['severity'] if active else None,
            'triggered_rules': rules['triggered_rules'], 'missing_information': missing,
            'risk_score': None, 'saved': False, 'source': 'existing-rule-engine', 'animal_id': animal['_id']}

