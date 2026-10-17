"""Conservative symptom-pattern heuristics, not a validated diagnostic protocol."""

from .features import SPECIES, symptom_set

DISEASE_LABELS = {
    'lsd': 'Possible Lumpy Skin Disease',
    'fmd': 'Possible Foot and Mouth Disease',
    'respiratory': 'Possible respiratory syndrome',
    'gastrointestinal': 'Possible gastrointestinal syndrome',
    'undifferentiated': 'Undifferentiated illness - veterinary assessment needed',
}


def evaluate_rules(report, animal):
    symptoms = symptom_set(report)
    species = animal.get('species')
    strengths = {'lsd': 0.0, 'fmd': 0.0, 'respiratory': 0.0, 'gastrointestinal': 0.0}
    flags = []
    fever = 'fever' in symptoms
    if report.get('temperature_c') is not None and report['temperature_c'] >= 39.5:
        flags.append('TEMP_SIGNAL: measured temperature at or above the prototype 39.5 C alert threshold.')
    if 'skin_lesions' in symptoms:
        if species in ('cattle', 'buffalo'):
            strengths['lsd'] = 0.60 + 0.25 * fever + 0.15 * ('swelling' in symptoms)
            flags.append('LSD_PATTERN: skin lesions in an eligible bovine species; fever/swelling increase pattern strength.')
        else:
            flags.append('LSD_SPECIES_EXCLUDED: this model does not suggest LSD for this species; investigate other skin conditions.')
    if 'mouth_foot_lesions' in symptoms and species in SPECIES:
        strengths['fmd'] = 0.65 + 0.20 * ('drooling' in symptoms) + 0.15 * fever
        flags.append('VESICULAR_PATTERN: mouth/foot lesions; urgent veterinary review and laboratory differentiation recommended.')
    if 'cough' in symptoms:
        strengths['respiratory'] = 0.55 + 0.20 * ('nasal_discharge' in symptoms) + 0.15 * fever + 0.10 * ('weakness' in symptoms)
        flags.append('RESPIRATORY_PATTERN: cough with associated respiratory/systemic observations; cause is unspecified.')
    if 'diarrhea' in symptoms:
        strengths['gastrointestinal'] = 0.60 + 0.20 * ('weakness' in symptoms) + 0.20 * (report.get('appetite', 'normal') != 'normal')
        flags.append('GASTROINTESTINAL_PATTERN: diarrhea with weakness/appetite context; cause is unspecified.')
    urgent = report.get('mortality_count', 0) > 0 or report.get('activity') == 'recumbent'
    if report.get('mortality_count', 0) > 0:
        flags.append('MORTALITY_ALERT: reported deaths require immediate professional assessment regardless of model output.')
    if report.get('activity') == 'recumbent':
        flags.append('RECUMBENCY_ALERT: animal unable to stand; immediate veterinary contact recommended.')
    severe_measurements = report.get('appetite') == 'none' or (report.get('temperature_c') or 0) >= 41
    if report.get('appetite') == 'none':
        flags.append('APPETITE_ALERT: no appetite reported; professional assessment recommended.')
    if (report.get('temperature_c') or 0) >= 41:
        flags.append('SEVERE_TEMPERATURE: at or above the prototype 41 C severe-observation threshold; urgent review recommended.')
    strongest = max(strengths.values())
    severity = 'critical' if urgent else ('high' if strongest >= 0.85 or 'mouth_foot_lesions' in symptoms or severe_measurements else ('moderate' if symptoms else 'low'))
    return {'strengths': {key: round(value, 4) for key, value in strengths.items()},
            'triggered_rules': flags, 'severity': severity, 'urgent': urgent}
