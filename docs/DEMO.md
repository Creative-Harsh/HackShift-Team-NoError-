# SIH demonstration runbook

The local seed is synthetic and idempotent. Every demo account uses `Demo@26128`:

| Role | Email |
| --- | --- |
| Farmer | `farmer@demo.pashuraksha.in` |
| Paravet | `paravet@demo.pashuraksha.in` |
| Veterinarian | `vet@demo.pashuraksha.in` |
| Laboratory | `lab@demo.pashuraksha.in` |
| Admin | `admin@demo.pashuraksha.in` |

1. Start MongoDB, the API and the frontend. Use `npm run build` followed by `npm run preview -- --host 127.0.0.1 --port 4173` for the offline demonstration. Check `GET /api/health` reports `database: mongodb`. To rehearse from the beginning without deleting old records, start a development API using a new `MONGODB_DATABASE` name and `DEMO_MODE=true` as described in [deployment](DEPLOYMENT.md).
2. Farmer opens **My animals**, looks up simulated Pashu ID `261280000001`, and submits fever + skin lesions + swelling with an overdue vaccination status. The case shows Possible Lumpy Skin Disease, explainable factors and safe actions. It remains a preliminary assessment.
3. Admin opens **Outbreak map** and clicks **Replay next report**. Each click persists one synthetic observation through the normal report, triage, risk and outbreak services. One report is isolated; three similar nearby animals form an abnormal cluster; five or more can become a suspected outbreak. The map displays markers, density, filters and exact cluster factors.
4. Veterinarian opens a high-risk case, claims it, records clinical findings/recommendations and requests LSD PCR (or another supported category). The timeline changes to `vet_assigned`, `vet_review`, `sample_requested`.
5. Laboratory moves the request through `received` and `testing`, then enters positive, negative or inconclusive findings. Positive confirms the requested case category only; final results are immutable and are copied into the animal history.
6. Veterinarian records a control/treatment note and closes the episode. No medication or dosage is generated.
7. Admin reviews the active cluster. Official `confirmed_outbreak` requires a matching positive test, current confirmed case and an investigation note. Replay never sets this state automatically.
8. For offline reporting, load the report screen while online, optionally select a photo/voice file, disconnect, submit and verify **Saved offline — waiting to sync**. Reload in the same tab; the shell, cached animal selector and per-user IndexedDB queue remain. Reconnect with the same user and verify **Synced successfully** and exactly one server case. The actual observation timestamp is preserved. A different account cannot submit the queued row. See [offline recovery](OFFLINE.md) for expired-session and storage behavior.

Browser artifacts include `.runtime/phase3-browser.json`, `.runtime/phase4-browser.json`, `.runtime/phase5-browser.json`, `.runtime/layout-browser.json` and `.runtime/install-browser.json`. They record calculated responses, factor totals, cluster states, durable synchronization and runtime errors. Data, identity and laboratory records are simulated; no government or external laboratory system receives anything. OpenStreetMap supplies public basemap tiles when connected.

For the optional **PashuMitra** demonstration, click the calf, select Hindi/Hinglish and describe `Meri gaay ko bukhar hai aur khana nahi kha rahi do din se`. Enable page guidance, load/select Gauri inside the companion, and verify the readback. The existing rule engine flags urgent attention for not eating. Ask how to report, follow its highlight yourself, and complete the actual form. Ask for status on the resulting case page. Browser speech requires its separate permission and a working browser speech service; text mode works without a provider key. The [companion walkthrough](PASHUMITRA.md) covers exact steps and measured limitations.
