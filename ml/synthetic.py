"""Synthetic latent-class generator with overlapping symptoms and missingness.

All distribution parameters below are engineering choices, not measured disease
prevalence, clinical sensitivity or government surveillance data. Labels are
sampled first; no production rule or classifier generates the target label.
"""

from datetime import datetime, timedelta, timezone
from random import Random

REFERENCE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)
GENERATOR_VERSION = 'synthetic-livestock-v1'
CLASSES = ('lsd', 'fmd', 'respiratory', 'gastrointestinal', 'undifferentiated')
SYMPTOMS = ('fever', 'cough', 'nasal_discharge', 'drooling', 'skin_lesions',
            'mouth_foot_lesions', 'diarrhea', 'weakness', 'swelling')
# Bernoulli observation frequencies chosen to produce overlap and ambiguous rows.
OBSERVATION_FREQUENCIES = {
    'lsd':             (.86, .08, .18, .08, .93, .03, .05, .52, .72),
    'fmd':             (.78, .05, .12, .85, .04, .94, .08, .44, .13),
    'respiratory':     (.68, .91, .81, .07, .03, .02, .09, .42, .08),
    'gastrointestinal':(.38, .07, .09, .07, .03, .02, .92, .68, .08),
    'undifferentiated':(.28, .20, .20, .17, .24, .17, .21, .31, .19),
}


def generate_dataset(per_class=800, seed=26128):
    rng = Random(seed)
    rows = []
    for label in CLASSES:
        for _ in range(per_class):
            eligible = ('cattle', 'buffalo') if label == 'lsd' else ('cattle', 'buffalo', 'goat', 'sheep', 'pig')
            species = rng.choice(eligible)
            signs = [symptom for symptom, frequency in zip(SYMPTOMS, OBSERVATION_FREQUENCIES[label]) if rng.random() < frequency]
            temperature = round(rng.uniform(39.6, 41.2) if 'fever' in signs else rng.uniform(37.5, 39.4), 1)
            # Missing temperature and occasional conflicting owner observations.
            if rng.random() < .12:
                temperature = None
            elif rng.random() < .06:
                temperature = round(rng.uniform(37.5, 41.2), 1)
            appetite = rng.choices(('normal', 'reduced', 'none'), weights=(.22, .63, .15))[0]
            if label == 'undifferentiated':
                appetite = rng.choices(('normal', 'reduced', 'none'), weights=(.65, .3, .05))[0]
            status = rng.choices(('up_to_date', 'overdue', 'unknown'), weights=(.25, .48, .27))[0]
            report = {
                'symptoms': signs, 'temperature_c': temperature, 'appetite': appetite,
                'milk_drop_percent': round(rng.uniform(0, 55), 1) if species in ('cattle', 'buffalo') and rng.random() < .75 else 0,
                'activity': rng.choices(('normal', 'reduced', 'recumbent'), weights=(.32, .64, .04))[0],
                'recent_contact': rng.random() < (.35 if label == 'undifferentiated' else .62),
                'vaccination_status': status, 'mortality_count': 1 if rng.random() < .04 else 0,
                'duration_hours': round(rng.uniform(2, 168), 1),
            }
            animal = {'species': species, 'age_months': rng.randint(2, 180),
                      'vaccination_history': [], 'disease_history': []}
            if rng.random() < .58:
                # EHR vaccine type must not leak the latent disease target.
                vaccine = rng.choice(('LSD', 'FMD')) if species in ('cattle', 'buffalo') else 'FMD'
                animal['vaccination_history'].append({'vaccine': vaccine,
                    'date_given': (REFERENCE_TIME - timedelta(days=420 if status == 'overdue' else 90)).date().isoformat(),
                    'next_due_date': (REFERENCE_TIME + timedelta(days=-55 if status == 'overdue' else 270)).date().isoformat()})
            if rng.random() < .14:
                animal['disease_history'].append({'diagnosis': 'Synthetic prior illness',
                    'date': (REFERENCE_TIME - timedelta(days=rng.randint(1, 200))).date().isoformat()})
            rows.append({'report': report, 'animal': animal, 'label': label, 'is_synthetic': True})
    rng.shuffle(rows)
    return rows
