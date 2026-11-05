# Outreach & Validation Plan: ELS Platform (Nov 2026 to mid-Feb 2027)

## Context

The work is real: a pipeline, the Explorer, an arXiv-ready paper, and Medium articles. But almost nobody outside the project has seen it. For the NIW petition (filing in 6 to 12 months), USCIS needs evidence from people other than you. That means independent experts saying the work matters nationally, organizations using or validating it, peer-reviewed publication, and invitations to talk about it. This plan uses the next ~15 weeks to produce that evidence. Outreach goes in tiers: warm-up contacts first to test the pitch, then heavy hitters.

Inputs set:
- Audiences: **state ECE agencies, ECE policy researchers, curriculum/edtech companies**.
- 15+ hours a week.
- Explorer is public, but **every state is currently subset data**, so full data is a prerequisite for outreach.
- **FL can be added easily.**
- **The Planning app is being dropped** (child-safety liability).
- **AIED 2027 is the primary paper target.**

**Guiding rule: every touch aims at one NIW artifact.** These are (a) proof of use, (b) a data-accuracy validation, (c) a future letter writer, (d) an invitation to speak or present, (e) a citation, publication, or press mention. Confirm the evidence mix with an immigration attorney before Month 3. In particular, ask how independent letters weigh against letters from collaborators, and which publications count most (this plan is not legal advice).

---

## Timeline at a glance

| Weeks | Dates | Main work |
|---|---|---|
| 1-2 | Nov 2-15 | Post arXiv, then fix `age_band`; submit DAI workshop paper; drop Planning app; clean up Medium; website overhaul; tracker |
| 2-5 | Nov 9-Dec 6 | **Full data, round 1** (6 annotated states + FL), with human review; **Phase 1 warm-up outreach** from Nov 16 |
| 6-7 | Dec 7-18 | **Phase 2** begins (staff in covered states, data-standards orgs, curriculum companies) |
| holiday | Dec 19-Jan 3 | **Full data, round 2** (Tier-1 target states); start AIED rework; draft the first magazine piece |
| 10-14 | Jan 4-Feb 6 | **AIED rework & submission** (top priority, ~8 hrs/wk); Phase 2 continues to Jan 17 |
| 12-15 | Jan 18-Feb 14 | **Phase 3 heavy hitters**, now able to cite full data, state validations, and a submitted paper |

---

## Phase 0: Foundations (Weeks 1-2, Nov 2-15)

### 0.1 Paper
- **Post arXiv v1.** Upload `paper/arxiv_submission/arxiv_upload.tar.gz` (built 2026-11-01). It is the credibility anchor every email links to, and it timestamps priority before the AIED rework.
- **Submit to AAAI-27 Deployable AI Workshop** (deadline 2026-11-20, `paper/dai2027/` already drafted). It is non-archival, so it does not block AIED, and it may give you a presentation at an AAAI-affiliated event. Check `paper/dai2027/main.tex` for any Planning-app mention before submitting.

### 0.2 Drop the Planning app (site, docs, infra, articles)
- **Site:** remove "Parent Planning Tool" from `packages/landing-site/src/data/projects.ts` and article 3 from `data/articles.ts`. Check `PrivacyPage.tsx` / `TermsPage.tsx` for planning or child-data language and remove it.
- **Live deployment:** take `planning.edtechco.org` offline, because a live public URL is where the liability sits. Tear down the deployed planning stack and the AgentCore agent (`infra/cdk/lib/planning-stack.ts`, deployed with `scripts/deploy_planning_app.sh`). First confirm there is no stored user or child data that has to be exported or deleted under the privacy policy. This step needs your explicit go-ahead.
- **Code and docs stay.** `packages/planning-*`, `packages/agentcore-agent`, and the existing docs are left as they are, so the app could still be redeployed. Optionally add one line to `README.md` marking the Planning app as "not currently deployed or supported".
- **Paper:** `paper/sections/conclusion.tex:36` only says "planning tools" generically, so no change is needed.

### 0.3 Medium cleanup (~4-6 hrs)
- **Article 3** ("From Standards to Story Time") is entirely about the Planning app. **Unpublish it** rather than just unlisting it, so it no longer reads as an offered product.
- **Articles 1, 2, 4, 5**: remove or reword Planning-app references. Article 5's "Automated Plan Generation" section gets cut or recast as a general downstream use, with no product. Fix the `link-to-article-N` placeholders in the local copies (`documentation/medium-articles/`) and link each article to `/research`.
- Bring numbers in line with the paper (e.g. 297 audited detections, the corpus-tier wording), so nothing public contradicts it.
- **No new Medium articles.** New writing goes to edited publications (see "NIW-meaningful channels").

### 0.4 Website overhaul (`packages/landing-site`)
Switch from hash routing (`App.tsx` `hashToPage`) to **real paths**. CloudFront already sends 403/404 back to `index.html` (`infra/cdk/lib/landing-site-stack.ts:104`), so no infra change is needed. Redirect the old `#privacy`/`#terms`/`#contact` links.

| Path | Purpose | Key content |
|---|---|---|
| `/research` | Paper landing page | Plain-language summary. Headline numbers: recall 1.000 at every level across 6 states; 297 detections audited by hand, 1 hallucinated. Method figure, then arXiv link and BibTeX. |
| `/data` | What "machine-readable" means | Side-by-side: a PDF snippet and its structured record (e.g. KY `Benchmark 1.1` → `US-KY-2021-AL.1.1.EASPT`). Schema diagram, coverage map (full vs. coming soon), sample JSON/CSV, **"Request your state"** button. |
| `/for-states` | State agencies | QRIS/alignment pain point, your state in the Explorer, **"Validate your state's data"** request |
| `/for-researchers` | Policy researchers | A worked cross-state comparison (e.g. self-regulation at age 4 across the loaded states), data access, collaboration invite |
| `/for-curriculum` | Curriculum/edtech | A worked alignment crosswalk, data-access interest form, pilot invite |
| `/about` | Profile and NIW exhibit | Bio, publications, talks, press. Grows over the window. |

Also:
- New Hero tagline ("Every state's early learning standards, as structured data") with 3 audience buttons.
- `data/publications.ts`.
- Contact-reason dropdown in `ContactPage.tsx`.
- Analytics that respect privacy on the site and the Explorer, because usage is type-(a) evidence. Disclose it in `PrivacyPage.tsx`.
- A 2-3 minute demo video, embedded on `/research` and `/data`.
- **A `/brief` page instead of a PDF attachment.** Cold emails with attachments are often caught by spam filters, and security-trained recipients (state agencies especially) are told not to open them. Put the one-page summary (problem, what it does, proof, ask) on a printable web page. The link also shows up in analytics, so you can see who opened it.

### 0.5 Outreach infrastructure
- **Contact tracker** (an artifact with a shared database, or a spreadsheet). Columns: name, org, role, tier, audience, why them, source, channel, dates, response, outcome type (a-e), letter candidate, independent (Y/N), evidence link.
- **Evidence folder**: every positive reply, usage confirmation, and invitation saved as a dated PDF the day it arrives.
- **3 email templates**, one per audience. Keep each to 120 words or fewer, with one link and one small, specific ask. Never open by asking for a letter.

---

## Full data for target states (Weeks 2-5 and the holiday break)

Today every state in the Explorer is the `_only_subset` tier. A state contact who sees 15 pages of their 100-page document loses trust immediately. Target the **`_trimmed` tier**, which keeps 100% of standards and cuts pages only (memory: corpus tiers).

**Step 0 (Week 1, right after the arXiv v1 upload): fix the `age_band` defect.** A state reviewer would notice it. The fix follows CLAUDE.md "Where `age_band` destabilizes at scale" and has two halves:
- A rule-8 prompt clause: `age_band` comes only from a side-by-side column that distinguishes siblings, never from a page banner or running header.
- `_dedup_elements` stops keying on `age_band`.

Then:
- A/B it against **CA and TX**, whose real age-band columns it must not suppress, and against KY (duplicates and fabricated `.N` keys should go to 0). Use CO as the control.
- The fix moves `code_version_hash`. That is accepted: the AIED rework re-records the affected measurements at the new hash.
- Update the CLAUDE.md section from "OPEN DEFECT" to fixed, with the measured result.

**Round 1 (Nov 9-Dec 6): the 6 annotated states + FL**, run on the fixed build.
- `_trimmed` PDFs already exist for AZ, KY, NV, TX, and CO (`colorado_3_5_trimmed_2020.pdf`).
- CA runs on its own document. No trimmed version is needed.
- **FL is new**: source the current Florida early learning standards document.
- Pace: **about one full state per day** (Bedrock Opus daily quota), plus review time.

**Round 2 (Dec 19-Jan 3): the home states of the Tier-1 targets.** That is likely 4-8 more states, chosen once the Tier-1 list exists.

**Quality gate per state, before it goes public:**
- Check `total_elements`, the merge `error` string, and per-page coverage. Do not trust a `SUCCEEDED` status alone (the KY silent 60% loss).
- Check for **same-page rows that share parents and indicator name**, and for `.N` suffixed `standard_id`s. After the fix there should be none; any that remain point to a surviving duplicate, not to a real collision.
- A human spot-check in the Explorer's verification layer.

---

## Phase 1: Warm-up tier (Weeks 3-5, Nov 16-Dec 6, ~60 contacts)

Purpose: test the pitch cheaply, collect testimonials and early users, and get introductions upward.
- ECE practitioners: childcare directors, ECE coaches, and QRIS coaches, especially in Arizona.
- ECE doctoral students and early-career faculty (ASU, U of Arizona, UBC as an alum connection).
- Small edtech or curriculum founders.
- A few learning-analytics researchers, to validate the method.

About 20 a week, with 2 follow-ups (day 5 and day 12). Thanksgiving week runs lighter.

**Gate before Phase 2:** at least 15% reply rate, at least 5 calls, a revised pitch, and at least 3 people actually using the Explorer. Under 5% means rewriting the template and landing page first.

## Phase 2: Mid tier (Dec 7-18 and Jan 4-17, ~60-80 contacts)
- **Staff in the 7 full-data states** (AZ, CA, CO, TX, KY, NV, FL): standards coordinators and QRIS leads, asked to "validate your state's data". Start with AZ.
- **Data-standards organizations**: CEDS (early learning domain), Ed-Fi, 1EdTech CASE, Achievement Standards Network, and CZI Learning Commons (K-12 standards graph, so you fill the early-learning gap).
- **Curriculum, assessment, and childcare platforms**: alignment teams at companies that map products to every state's ELS (Teaching Strategies, Frog Street, HighScope, Kaplan, Waterford, Brightwheel, and similar). Ask how many hours alignment costs them now.
- **Research and policy organizations, at staff level**: Child Trends ECDC, NIEER researchers, ECDataWorks, BUILD Initiative, Education Commission of the States, Alliance for Early Success.
- **Mid-career faculty** publishing on ECE standards, P-3 alignment, or ECE data systems.

Goals: 2-3 formal state reviews (b), 1-2 pilots (a), 1-2 webinar invitations (d), and 8-10 letter candidates.

## Phase 3: Heavy hitters (Jan 18-Feb 14, ~20-30 contacts)
Only start once Phase 2 has proof points to cite.
- **Leading scholars of state ELDS**: Catherine Scott-Little and Sharon Lynn Kagan (verify affiliations), NIEER leadership, Child Trends early-childhood leads, P-3 alignment researchers. These are the best independent letter writers.
- **State leadership**: state early childhood directors, NAECS-SDE (the network of state ELS owners), CCSSO early learning.
- **Federal**: ACF Office of Early Childhood Development, Office of Head Start (ELOF), NCECDTL, Child Care State Capacity Building Center. The aim is feedback, use, and invitations rather than letters.
- **Funders**, for support: Bezos Family Foundation, Heising-Simons, Overdeck, Gates, CZI, Buffett Early Childhood Fund. Ask for a conversation, not money.
- **Leadership at the largest curriculum publishers.**

Tactic: every email carries a **personalized artifact** (their state as full structured data, compared with others) and one ask, plus a warm introduction wherever one exists.

---

## AIED 2027 paper (primary publication target)

AIED 2027 runs in Adelaide, 18-23 Jul 2027, alongside EDM and L@S. **The call is not yet published. Best guess from past cycles: abstract about late January, full paper about early February 2027.** Re-check the call weekly from mid-November and adjust the dates below.

- **Week of Nov 16:** read the AIED 2026 call/CFP for format and policy as a proxy. Likely points: Springer LNCS, full papers about 12 pages plus references, short papers available, double-blind review, arXiv preprints allowed. Confirm each one. **Create or confirm the conference-system account now**, so the OpenReview mistake does not repeat.
- **Dec 19-Jan 3 (light):** reframe the outline for an AI-in-education audience. Lead with educational and policy impact (standards as infrastructure for alignment, QRIS, and research) and the human verification layer. Keep the method and the audit discipline as the technical core, and use the cross-state comparison as the "so what" example.
- **Jan 4-Feb 6 (about 8 hrs/wk, top priority):** rework sections, convert to LNCS, and anonymize. **Re-record at the post-fix hash** every measurement the `age_band` fix touches. At minimum that is the detector arms (Task 1 and Task 2; about 315K Opus tokens, roughly 12% of a day's quota, spread over 2-3 days) and the KY scale and stability numbers that cite the duplicate counts. Regenerate tables with `python paper/analysis/generate_tables.py`. Cite full-data coverage where it strengthens the claims. Do a final read-through the week before the deadline.
- Start the re-record in the **holiday window** so the quota never competes with Round 2 state runs.
- **Fallback if rejected** (decisions are probably around April): ACL 2027 Industry Track or ICDAR-type venues for the next cycle. Choose after the decision; do not dual-submit.

---

## NIW-meaningful channels (curated)

Only items whose output is strong evidence: peer-reviewed or archival publication, presenting at a nationally recognized venue, invited talks, or editorial publications and press. Dates are best guesses; verify each.

| Channel | Why it counts | Timing (best guess) |
|---|---|---|
| **AIED 2027** | Top peer-reviewed AI-in-education venue. Archival publication. | Submit early Feb 2027 |
| **AAAI-27 Deployable AI Workshop** | Already drafted, costs little. A presentation at an AAAI-affiliated event. | Nov 20, 2026 |
| **NAEYC Annual Conference 2027** (proposal) | The largest national ECE professional gathering, held every year (2025, and the 2026 centennial in DC), reaching the practitioner and state audience | The 2027 call is not posted yet. Watch naeyc.org/events from January. |
| **NAEYC Annual 2026, Dec 5-8, Washington DC** (attend) | Not evidence in itself, but the single best in-person chance to meet state ECE staff, researchers, and curriculum companies during Phase 2. Bring the Explorer on a laptop and follow up within a week. | Register now if budget allows |
| **Invited webinars and talks** from outreach (Child Trends, NIEER, state agencies, CEDS community) | Invited talks are strong independent evidence | Phases 2-3 |

**Editorial publications instead of Medium:** 2-3 pitched pieces over the window, chosen by audience.
- **Policy and general education:** an op-ed or guest essay for EdSurge, The 74, or the Hechinger Report.
- **Practitioner, peer-reviewed or edited:** NAEYC *Young Children*, or *Exchange* magazine for ECE leaders.
- **Policy or social-impact framing:** *Kappan* or *Stanford Social Innovation Review*.

Pitch the first piece in December, timed to "full data for 7 states" as the news hook. An editor-accepted piece or coverage of your work counts far more than self-published posts.

## Letters strategy (seeded now, collected in months 4-9)
- 5-7 letters, mostly from **independent** experts. Mix: 2-3 ECE scholars, 1-2 state agency or data-standards people, 1 company that used it, and optionally 1 AI/NLP researcher.
- Ask only after a real interaction such as a review, call, or pilot. Follow attorney guidance on drafting.

## Weekly operating rhythm (15+ hrs)
- **Nov-Dec:** about 8 hrs outreach, 4 hrs site/data/pipeline review, 3 hrs calls and evidence.
- **Jan to the AIED deadline:** about 8 hrs paper, 5 hrs outreach, 2 hrs calls and evidence.
- **Friday review:** sent / replies / calls / validations / users / invites / letter candidates, plus one change to the pitch.

---

## Build work I'd implement after approval (in order)
1. Remove the Planning app from the landing site. Take the live deployment down only with your go-ahead. Code and docs stay.
2. Landing-site routing, the 6 new pages plus `/brief`, Hero copy, contact-reason dropdown, analytics, and tests.
3. Edits to the Medium article copies in `documentation/medium-articles/`. You apply them on Medium.
4. Fix the `age_band` defect after arXiv v1 is posted, A/B it on CA, TX, KY, and CO, and update CLAUDE.md.
5. Full-data runs, round 1: the 5 `_trimmed` PDFs, CA's own document, and FL. Run the pipeline with the per-state quality gate and load the results to the Explorer.
6. Contact tracker, then contact-list research in waves (Tier 3, then 2, then 1, verified against current org pages).
7. Email templates, demo-video script, and magazine pitch drafts.
8. AIED: confirm the call, set up the LNCS skeleton, outline the reframe, then the re-record over the holidays.

## Verification
- **Site:** `pnpm --filter @els/landing-site test && pnpm --filter @els/landing-site build`, then a browser-pane preview of every route, deep-path loads, old hash redirects, and mobile width. Deploy to dev and confirm a deep link works on CloudFront.
- **Planning removal:** no Planning link or article is left on the landing site, and `planning.edtechco.org` no longer serves once teardown is approved.
- **`age_band` fix:** `pytest tests/ -v` passes; the A/B shows KY duplicates and `.N` keys at 0, CA and TX age bands unchanged, and CO unchanged.
- **Full data:** the per-state quality gate above, recorded in the tracker before a state is shown to anyone.
- **Outreach:** phase gates and weekly metrics.
