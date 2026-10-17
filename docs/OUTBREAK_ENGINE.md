# Outbreak engine design

The Phase 3 outbreak engine is implemented and verified with deterministic unit scenarios, real MongoDB geospatial queries and a clean browser replay. The thresholds are prototype surveillance inputs, not epidemiological validation.

The engine uses incident observation time, distinct animals and local disease/symptom similarity. It never consumes an LLM output or the case risk score. This prevents circular amplification when cluster context later contributes to case risk.

## Implemented bounded neighborhood algorithm

1. Select district cases in the configurable active window (default72hours). Exclude rejected and undifferentiated assessments. Keep server receipt time separately so offline batches do not look like simultaneous disease onset.
2. Find nearby observations within a configurable radius (default5km). MongoDB nearby APIs use GeoJSON, a real `2dsphere` index and distances in metres. Pure deterministic scoring uses the same haversine geometry.
3. Deduplicate by animal. One animal with many repeat reports contributes one current observation. Similarity combines same suspected disease and Jaccard overlap of the selected symptom sets.
4. Form bounded groups; membership must not allow an unlimited chain of individually nearby cases to merge remote villages. Score only groups with at least three distinct animals. A minimum evidence count is a guard, not the outbreak rule.
5. Score distinct-animal burden, spatial tightness, time concentration, symptom agreement, growth in successive24hour periods, excess over the local historical baseline and vaccination gaps. Every integer contribution is returned alongside its inputs.
6. Default states: score40+ Abnormal Cluster; score65+ and sufficient distinct evidence Suspected Outbreak. Score80+ marks critical intensity. These are prototype configurable surveillance thresholds, not validated epidemiological thresholds.
7. Match recalculated groups to existing groups by membership overlap, preserving cluster identity and any professional confirmation record. Store active/current state separately from historical confirmation evidence.

## Score budget

| Factor | Maximum points | Input |
|---|---:|---|
| Distinct affected animals |20|Number of unique animals, with saturation|
| Spatial concentration |15|Mean distance relative to configured radius|
| Time concentration |15|Observation span relative to active window|
| Symptom/disease similarity |15|Pair agreement, excluding unknown syndromes|
| Recent growth |15|Smoothed recent24h/prior24h ratio|
| Historical excess |15|Active incidence divided by local expected incidence|
| Vaccination gap |5|Relevant overdue/unprotected proportion|

Historical baseline is a clearly labelled demo history for seeded scenarios. A floor on expected incidence avoids division by zero. No weather points are added without an actual configured, documented weather signal.

## Confirmation boundary

A laboratory positive result can confirm an individual case. It must not automatically declare an official outbreak. Outbreak confirmation is a separate district-admin action with an explicit note and linked positive laboratory evidence. The prototype records an authorized simulated workflow; it does not notify or write to a government system.

## Verification scenarios

- A: observations far apart -> no active cluster.
- B: nearby observations months apart -> no active cluster.
- C: distinct animals, matching symptoms, nearby and recent -> cluster.
- D: concentrated observations arriving rapidly above local baseline -> critical cluster.
- Repeat reports for one animal must not inflate cluster size.
- Higher historic activity reduces the historical-excess contribution.
- Rejected cases leave the active disease signal.
- Every factor sum equals its displayed cluster score.
- Real MongoDB tests separately verify radius units and the actual spatial index.

`ml/outbreak_evaluation.json` records zero alerts across six designed negative scenarios and detection of both designed positive scenarios. Scenario C scores 66 and scenario D scores 95 (critical intensity). In one fixed replay, the first abnormal alert precedes a toy sixth-report comparator by 18 hours and suspected status precedes it by 6 hours. These small, constructed denominators and the comparator do not estimate field performance. See [evaluation details](EVALUATION.md).

## Persistence and age-out

Reports trigger district recalculation; map/list polling refreshes a projection older than 30 seconds so clusters expire even without new reports. Current risk uses the immutable animal context captured at report time plus current spatial evidence. Expired spatial contributions are cleared. Initial risk remains stored unchanged. Latest rejected or unknown observations suppress older same-animal suspicion for both clusters and nearby-risk counts. Recently closed episodes remain incidence evidence until the window expires; they are excluded from unresolved operational workload.

The single-worker prototype serializes projection writes with a process lock. Report UUID retries repair interrupted projections. More than 5,000 observations in the baseline plus active window or 2,000 eligible active animals produces an explicit capacity error, retaining the stored report; it never silently calculates on truncated evidence. Production scaling needs district jobs with distributed leases and workload partitioning.
