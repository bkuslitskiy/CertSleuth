# Badge/cert import sources — endpoint verification (2026-07-17)

Empirical verification of the four candidate importers beyond Credly. Same risk posture
as the Credly importer (D6): domain-pinned direct fetch of structured data, no LLM,
unofficial endpoints re-verified before each importer is built. All fetches below were
performed live on 2026-07-17.

## 1. Microsoft Learn transcripts — CONFIRMED (unofficial endpoint, official feature)

- **Feature (official):** users generate a public share link from Learn profile →
  Transcript → "Share link". Docs (updated 2025-06):
  https://learn.microsoft.com/en-us/credentials/certifications/view-share-transcript
- **Endpoint (unofficial):**
  `GET https://learn.microsoft.com/api/profiles/transcript/share/{shareId}?locale=en-us`
  Returns JSON: `certificationData.activeCertifications[]` (name, certificationNumber,
  status, dateEarned, expiration), `appliedSkillsData.appliedSkillsCredentials[]`
  (credentialId, title, awardedOn), `modulesCompleted[]`.
  Community write-up: https://dev.to/wyattdave/using-microsoft-learn-api-to-validate-power-platform-makers-2moh
- **Verified:** dummy shareId returns a clean API `404` (route live, wants a valid ID).
  Full validation needs a real share link — generate one from any Learn profile.
- **Import shape:** paste-share-link flow, regex-pin `learn.microsoft.com/api/profiles/transcript/share/`.
- **Caveats:** undocumented — Microsoft may change it without notice. Certiport-earned
  MS certs may not appear until MS finishes Certiport/Learn integration (per official doc).

## 2. Accredible / credential.net — CONFIRMED LIVE (unauthenticated public endpoint)

- **Endpoint (unofficial, tested live):**
  `GET https://api.accredible.com/v1/credential-net/credentials/{id}` — no auth for
  public credentials. Verified against Accredible's demo credential 10000005: returns
  full JSON (`name`, `description`, `issued_on`, `expired_on`, `uuid`, `learning_outcomes`,
  group/issuer data). Private credentials excluded by design (`"private": false` field).
- **Official API (org-scoped, key required):** https://docs.api.accredible.com —
  `api.accredible.com/v1/credentials/{id}` returns 401 without a key (verified).
  Not usable for user-side import; documented here for completeness.
- **Import shape:** paste-credential-URL flow. Accept `credential.net/<id>` and branded
  domains (credentials.databricks.com, google.accredible.com, …), extract the numeric
  id / uuid, hit the credential-net endpoint. Covers Google Cloud, Databricks, HubSpot, Slack.
- **Caveats:** per-credential, not per-profile — one paste imports one credential.
  Directory search exists (directory.credential.net) but is org-opt-in and JS-heavy; skip.

## 3. Open Badges (Badgr / Canvas Credentials / any OB issuer) — CONFIRMED (official spec)

- **Spec:** OB 3.0 final since June 2024 (aligned with W3C Verifiable Credentials v2):
  https://www.imsglobal.org/spec/ob/v3p0 · candidate-final text:
  https://1edtech.github.io/openbadges-specification/ob_v3p0.html
  OB 2.0 remains widely deployed; verification is (a) hosted public JSON or (b) signed JWS.
- **Baking:** PNG (`openbadges` iTXt chunk) and SVG (namespaced assertion) embedding is
  spec-defined in both 2.0 and 3.0 — file upload alone yields the full assertion.
- **Import shape:** spec §5.3 as planned — upload .png/.svg/.json, parse baked assertion,
  verify hosted JSON where present. Handles private profiles on every OB platform.
- **Ecosystem signal:** Credly itself now accepts imported outside OB badges
  (https://support.credly.com/hc/en-us/articles/30107800919707) — OB is the lingua franca.

## 4. LinkedIn certifications CSV — CONFIRMED (official export)

- **Official doc:** https://www.linkedin.com/help/linkedin/answer/a1339364 — the data
  export "Contains licenses or certifications a member has obtained, including the
  issuing authority name or company, start date, finish date, and license number."
  Certifications category is in the ~10-minute export tier; CSV format; download link
  valid 72h. File ships only if the profile has certifications listed.
- **Import shape:** file-upload parser for `Certifications.csv` (`import_source`
  already reserves `linkedin_csv`). Exact column headers are not officially documented —
  pin them from a real export at build time (Boris can export his own in ~10 min).
- **Caveats:** No API; user-initiated export only. Names are free-text (no issuer IDs),
  so catalog matching is name-based — route misses through the same
  unmatched-badge → SourceSubmission queue as Credly.

## Build order recommendation

1. **Microsoft Learn** — biggest uncovered issuer; needs one real share link to pin the
   response schema.
2. **Open Badges upload** (spec §5.3) — issuer-agnostic backup for everything, covers
   private profiles.
3. **Accredible** — endpoint already proven; small parser.
4. **LinkedIn CSV** — cheap catch-all; needs a sample export to pin columns.
