"""Shared, deterministic EHR context; dates are evaluated at observation time."""

from datetime import date, datetime, timedelta, timezone

VACCINE_NAMES = {
    'lsd': {'lsd', 'lumpy skin disease', 'lumpy skin disease vaccine'},
    'fmd': {'fmd', 'foot and mouth disease', 'foot-and-mouth disease', 'fmd vaccine'},
}


def as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def observation_time(now):
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Assessment time must be timezone-aware.')
    return now.astimezone(timezone.utc)


def vaccination_context(report, animal, disease_code, now):
    """An FMD vaccine is not evidence of LSD vaccination. Latest valid dose wins.

    A conflicting self-report never cancels an overdue record. A newly reported
    overdue status is retained even if a stored due date is still current.
    """
    names = VACCINE_NAMES.get(disease_code)
    if not names:
        return {'status': 'not_applicable', 'source': 'no_specific_vaccine_mapping',
                'detail': 'No disease-specific vaccine mapping for this syndrome; no vaccine points.'}
    today = observation_time(now).date()
    records = []
    for item in animal.get('vaccination_history', []):
        if str(item.get('vaccine', '')).strip().lower() not in names:
            continue
        given, due = as_date(item.get('date_given')), as_date(item.get('next_due_date'))
        if given and due and given <= today and due > given:
            records.append((given, due, item))
    reported = report.get('vaccination_status', 'unknown')
    latest = max(records, key=lambda row: (row[0], row[1])) if records else None
    if latest:
        stored = 'overdue' if latest[1] < today else 'up_to_date'
        conflict = reported not in ('unknown', stored)
        status = 'overdue' if 'overdue' in (stored, reported) else stored
        detail = f"Latest relevant EHR vaccination due {latest[1].isoformat()}: {stored.replace('_', ' ')}."
        if conflict:
            detail += f" Reporter says {reported.replace('_', ' ')}; discrepancy needs verification; overdue signal retained."
        return {'status': status, 'source': 'ehr_and_report', 'detail': detail}
    if reported in ('overdue', 'up_to_date'):
        return {'status': reported, 'source': 'self_report',
                'detail': f"Self-reported {reported.replace('_', ' ')}; no dated matching vaccination in EHR."}
    return {'status': 'unknown', 'source': 'missing',
            'detail': 'Disease-specific vaccination status is unknown; verify vaccination record.'}


def recent_disease_history(animal, now):
    today = observation_time(now).date()
    for item in animal.get('disease_history', []):
        when = as_date(item.get('date') or item.get('diagnosed_at') or item.get('created_at'))
        if when and today - timedelta(days=90) <= when <= today:
            return True
    return False
