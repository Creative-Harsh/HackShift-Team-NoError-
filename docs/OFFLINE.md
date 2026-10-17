# Offline reporting and recovery

Open the **production build** over HTTPS or localhost and sign in while connected. The app's versioned service worker precaches the public HTML, CSS, JavaScript, manifest and icon, including lazy route bundles. It excludes private API responses and external map tiles. Failed static requests do not receive HTML disguised as an image or script.

The animal list is saved in IndexedDB for the current user. Offline lookup and the report animal selector use that snapshot. Animal detail clearly labels cached information and does not present missing recent reports as a zero count. A new login, new animal registration, clinical case history, professional workflow and live maps require a connection.

## Submission sequence

1. Generate one UUID for the report and one for each selected attachment. Capture the observation time when saving, separately from the server's receipt time.
2. Commit the structured payload and photo/voice blobs to IndexedDB in one transaction **before** attempting transmission or announcing the offline save. The saved report is immutable; creating another report gets a new UUID.
3. On startup, reconnect, every 15 seconds while open, or **Sync now**, obtain a browser Web Lock. Read only the current user's queue and capture that user's token.
4. Upload attachments using their stable UUIDs, persisting each returned private URL. Send the report with its stable client UUID and captured token. Check that the account/token still match before every operation.
5. Mark a successful row `synced`, retain its case link and discard its local attachment blobs. The per-user synchronization panel shows queued and successful counts.

An interrupted row marked `syncing` is eligible for retry after restart. MongoDB's unique `(reporter_id, client_report_id)` and `(uploaded_by, client_upload_id)` indexes guard against duplicate cases/files if a response is lost, a tab closes, or the browser lacks Web Locks. Identical retries return the original resource; reusing an ID for different content returns 409.

## Failure behavior

| Failure | Behavior |
| --- | --- |
| Offline, timeout or backend 5xx | Retain the report; exponential delay capped at 60 seconds; reconnect/manual retry supported |
| Expired/revoked JWT | Retain the report, clear the expired login, require the same user to sign in again |
| Another user signs in | Show and synchronize only that user's records; the first user's saved rows remain untouched |
| 400/403/404/409/422 | Mark `Needs attention`, display the actual server error, stop automatic resubmission; create a corrected report |
| 408/429 | Retain and retry after backoff |
| IndexedDB unavailable/full | Show the storage error; do not claim that the report was saved |

The initial online session uses `sessionStorage`, so offline reload works in the same tab. Closing the tab loses that login session; the durable queue remains, but signing in again requires connectivity. Synchronization is a foreground feature, without an OS/background-sync delivery guarantee. Offline reports keep their captured observation time, so a reconnect batch does not become a false simultaneous outbreak.

Queue data is application-scoped by user, but IndexedDB is not encrypted or isolated from someone with browser-profile access. Signing out preserves unsynced work intentionally. Use a trusted device; clearing site storage removes all cached/queued data. The browser may also evict storage under pressure.

## Reproduce the browser check

With the API in demo mode and the production preview on port 4173, run from the repository root:

```powershell
node tests/browser-offline.cjs
```

The test uses real Chrome network-disconnect controls, reloads offline, reconnects, compares stored photo bytes, retries the same report ID, revokes a session and switches farmer accounts. It inspects real IndexedDB and backend responses, checks mobile overflow and uncaught runtime errors, and writes `.runtime/phase5-browser.json` and screenshots. Set `FRONTEND_URL` to override the preview origin. Each test uses a new browser profile and creates labelled demo reports; it does not erase existing records.
