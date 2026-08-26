# Qualitative Coding in the Social Sciences — Methods, Rigor, Transparency, Competitors, and Expansion Avenues

**Prepared:** 2026-08-23
**Subject:** Research briefing for the Qualitative Coding Tool (this repository)
**Purpose:** Establish what qualitative coding actually requires as a *method*, what standards of rigor and transparency the field enforces, what comparable tools already do, and — the main deliverable — an enumerated set of concrete avenues for expanding this application.

---

## 0. How to read this document

- **Parts 1–3** are the methodological background: the steps of qualitative coding, the rigor expected, the transparency required. These are the *requirements* the tool is implicitly being judged against.
- **Part 4** covers the empirical evidence on LLM-assisted coding — what actually works, and what the failure modes are.
- **Part 5** is the competitive landscape.
- **Part 6** is an honest, code-grounded gap analysis of the app as it stands today.
- **Part 7** is the payload: **96 numbered expansion avenues**, grouped into nine themes, each with a rationale, a pointer into this codebase, and an effort/impact estimate.
- **Part 8** sequences them into a roadmap and names the ten highest-leverage bets.
- **Part 9** lists sources.

Effort is rated **S** (days), **M** (a couple of weeks), **L** (a month or more). Impact is rated ★ to ★★★★★ in terms of how much it moves the tool toward being defensible for published research.

---

# Part 1 — What qualitative coding is, and what its steps are

There is no single procedure called "qualitative coding." There are several **traditions**, each with its own sequence, its own vocabulary, and its own idea of what a "code" is. A tool that claims to support qualitative coding is really claiming to support some subset of these. Knowing which subset you support — and saying so — is itself a rigor requirement.

## 1.1 Saldaña's two-cycle framing (the umbrella)

Johnny Saldaña's *The Coding Manual for Qualitative Researchers* (now in its 4th edition) is the field's standard reference and organizes coding into **First Cycle** and **Second Cycle** methods.

- **First Cycle** — the initial pass that attaches codes to data. The 4th edition catalogues **35 first-cycle methods** grouped into families: grammatical, elemental (e.g. descriptive, in-vivo, process coding), affective (emotion, values, versus, evaluation coding), literary/language, exploratory, procedural, and theming-the-data methods.
- **Second Cycle** — the harder, more analytical pass: pattern coding, focused coding, axial coding, theoretical coding, elaborative and longitudinal coding. This is where codes are *classified, prioritized, integrated and synthesized* into categories, themes, and eventually theory.
- **Analytic memoing** runs alongside both cycles and is treated as a first-class part of the method, not a side note.

**The key structural insight for a software tool:** first-cycle coding is a *labeling* operation over data units; second-cycle coding is a *restructuring* operation over the codes themselves. They need different data models and different UIs. Most AI coding tools — including this one — implement only the first cycle.

## 1.2 Reflexive Thematic Analysis (Braun & Clarke)

The single most-cited analytic procedure in applied qualitative work. Six **phases** (explicitly *not* "steps"):

1. Familiarization with the data
2. Generating initial codes
3. Generating (searching for) initial themes
4. Reviewing and developing themes
5. Refining, defining and naming themes
6. Writing up

Braun & Clarke's later methodological writing (2019–2022) is largely a list of **misapplications** to avoid, and these are directly relevant to how an AI tool should behave:

- The phases are **recursive**, not linear — you move back and forth, splitting and collapsing themes.
- It is **not** a sorting exercise. Highlight → label → bundle → done produces "tidy code piles and weak analysis."
- Themes do **not** "emerge." They are *constructed* by the analyst; writing as if they emerged signals a misreading of the method.
- Themes are developed in Phases 3–5, not discovered in Phase 2. A tool that stops after producing codes has produced *inputs to* thematic analysis, not thematic analysis.
- Reflexive TA is interpretivist. Bolting a "quasi-positivist coding audit" (e.g. inter-rater kappa) onto it is a category error — see §2.3.

## 1.3 Qualitative Content Analysis (Hsieh & Shannon)

Three variants, distinguished by **where the codes come from**:

| Approach | Origin of codes | Typical use |
|---|---|---|
| **Conventional** | Derived inductively from the text | Describing a phenomenon with little existing theory |
| **Directed** | Derived from prior theory/research, then applied deductively | Extending or validating a theoretical framework |
| **Summative** | Keyword counts and comparisons, then interpretation of latent context | Manifest + latent content, quantifiable |

The three differ in coding scheme, code origin, and threats to trustworthiness. **This matters for the tool:** the app currently only does the conventional/inductive route (generate a codebook from data). Directed content analysis — *bring your own validated codebook* — is a distinct, equally common workflow and is arguably the one LLMs are best at (see §4.1).

## 1.4 Grounded Theory

The tradition that gave the field the word "coding." Sequence:

1. **Open coding** — fracture the data into concepts
2. **Axial coding** — relate categories to subcategories, identify conditions/consequences
3. **Selective coding** — integrate around a core category into a theory
4. Running throughout: **constant comparison**, **theoretical sampling** (the next data you collect is determined by the analysis so far), **memoing**, and **theoretical saturation**

Grounded theory is the tradition most hostile to batch automation, because *what you sample next depends on what you just learned*. A pipeline that samples a fixed random percentage up front (as this app does) is structurally incompatible with theoretical sampling — a gap, and an opportunity (see avenue #9 and #4).

## 1.5 The Framework Method (Ritchie & Spencer; Gale et al. 2013)

Popular in health services and policy research, and the most "engineerable" of the traditions. Five stages in the classic form (seven in Gale et al.):

1. Familiarization
2. Identifying a thematic framework
3. Indexing (applying the framework to the data)
4. Charting — summarizing data into a **matrix of cases (rows) × themes (columns)**
5. Mapping and interpretation

The **matrix** is the defining artifact. It makes cross-case comparison systematic. No matrix view exists in this app; adding one is a well-specified, high-value feature (avenue #3).

## 1.6 Codebook structure (MacQueen et al., 1998)

The de-facto standard structure for a code in team-based research has **six components**:

1. The code (label)
2. A **brief** definition
3. A **full** definition
4. **When to use** it (inclusion criteria)
5. **When *not* to use** it (exclusion criteria)
6. Example(s)

**Direct finding for this repo:** the generator prompt in `backend/scripts/codebook_generator.py` emits *Definition, Inclusion Criteria, Key Words, Example*. It is missing the **full/brief split** and — more importantly — the **exclusion criteria ("when not to use")**, which is the single component most responsible for improving inter-coder agreement in team settings. This is a one-line prompt change with outsized methodological payoff (avenue #11).

---

# Part 2 — What level of rigor is required

## 2.1 The baseline framework: trustworthiness (Lincoln & Guba)

Qualitative research does not claim validity/reliability in the quantitative sense. It claims **trustworthiness**, via four parallel criteria:

| Criterion | Quantitative analogue | Established by |
|---|---|---|
| **Credibility** | Internal validity | Prolonged engagement, persistent observation, triangulation, peer debriefing, member checking, negative case analysis |
| **Transferability** | External validity | Thick description of context so readers can judge applicability |
| **Dependability** | Reliability | A documented **audit trail** of procedures and analytic decisions |
| **Confirmability** | Objectivity | Demonstrating that interpretations are traceable to the data, not the researcher |

Two of these four — **dependability** and **confirmability** — are *fundamentally software problems*. They are about logging, provenance, and traceability. That is where a tool can contribute most and where this app has its largest unclaimed territory.

## 2.2 The techniques reviewers look for

A methods section in a credible qualitative paper will usually name several of:

- **Audit trail** — a dated record of every analytic decision and its rationale
- **Analytic memos** — the researcher's thinking, captured as it happens
- **Reflexivity / positionality statement** — who the researcher is and how that shapes the reading
- **Peer debriefing** — an outsider interrogating the analysis
- **Member checking** — returning interpretations to participants
- **Negative case analysis** — actively hunting for data that contradicts the emerging account
- **Triangulation** — across data sources, analysts, methods, or theories
- **Thick description** — enough context for transferability
- **Saturation** — a defensible stopping rule (see §2.4)

## 2.3 Inter-coder reliability: contested, but concretely specified

This is the most misunderstood rigor requirement, and the debate matters for product decisions.

**The argument against:** in interpretivist traditions (reflexive TA especially), multiple coders converging on identical labels is not evidence of truth — it can be evidence of a flattened, mechanical reading. Braun & Clarke explicitly reject IRR as a quality criterion for reflexive TA.

**The argument for:** in codebook-based, team-based, positivist-leaning, or policy-facing work, IRR improves systematicity, communicability and transparency; promotes reflexive dialogue within teams; and persuades sceptical audiences.

**Practical guidance (O'Connor & Joffe, 2020) — the numbers a feature spec needs:**

- If double-coding everything is not viable, **randomly double-code 10%** of data units as a minimum; **10–25%** is typical.
- Report **which statistic** was used and **why**, plus the raw figure and how disagreements were resolved.
- **Krippendorff's α** is increasingly preferred: it handles >2 coders, missing data, and nominal/ordinal/interval/ratio data.
- Thresholds commonly cited: **α ≥ 0.800** reliable; **0.667–0.800** acceptable for tentative conclusions; **< 0.667** insufficient.
- Cohen's **κ**: 0.61–0.80 substantial, > 0.80 almost perfect.
- All thresholds are acknowledged as **arbitrary**; higher bars are expected for medical/policy/financial consequences than for exploratory work.
- Note the well-known **kappa paradox**: with skewed marginals (most segments not coded with a given code), κ collapses even at 95%+ agreement — which is exactly the regime of social-media coding. **Gwet's AC1** is the recommended remedy, and the recent PLOS Digital Health study reports both (κ = 0.34 vs AC1 = 0.93 on the *same* data) precisely to make this point.

**Product implication:** IRR must be *offered and explained*, never *imposed*. The right design is: pick your tradition → the tool offers the rigor apparatus appropriate to it.

## 2.4 Saturation: the stopping rule

- **Code saturation** ("heard it all") — no new codes appear. Empirically reached at around **9 interviews** in Hennink et al.'s study.
- **Meaning saturation** ("understand it all") — no new dimensions or nuances of existing codes appear. Required **16–24 interviews** in the same study.
- **Information power** (Malterud) — an alternative to counting: required sample size depends on the study's aim breadth, sample specificity, use of theory, dialogue quality and analysis strategy.

**Product implication:** a tool that codes in batches can *compute* a code-accumulation curve almost for free and give researchers an evidence-based, reportable saturation argument. Nothing in the CAQDAS market does this well. (Avenue #8.)

## 2.5 What "rigor" means specifically when an LLM is in the loop

The literature now adds requirements that did not exist five years ago:

- **Report the model, version, and parameters.** A "GPT" citation with no version is unreproducible; models are deprecated and silently updated.
- **Report the exact prompts**, including system prompts, verbatim, usually in an appendix.
- **Report error/hallucination rates** measured on your own data, not the vendor's benchmark.
- **Verify quotes.** Every AI-attributed excerpt must be checkable against the source.
- **Human adjudication remains mandatory** for interpretive claims.
- **Guard against "LLM hacking"** (§4.3) — the sensitivity of your conclusions to arbitrary model/prompt choices.

---

# Part 3 — What kind of transparency is required

Transparency is a *separate* requirement from rigor: rigor is about doing the analysis well; transparency is about others being able to see that you did.

## 3.1 Reporting standards

| Standard | Items | Scope |
|---|---|---|
| **COREQ** (Tong et al., 2007) | 32 | Interviews and focus groups, health/clinical/nursing |
| **SRQR** (O'Brien et al., 2014) | 21 | Any qualitative study, any discipline |
| **ENTREQ** | — | Qualitative evidence synthesis |

Both COREQ and SRQR **predate generative AI**. Neither asks for prompts, model parameters, or human–AI interaction logs. This is a documented gap, and it is being filled by newer instruments (§3.2).

## 3.2 AI disclosure: the emerging requirements

**Publisher/editor policy (settled):**
- COPE's 2023 position — AI **cannot be an author**; use must be disclosed. Endorsed by ICMJE, JAMA, WAME.
- **Where to disclose:** AI used for *writing* → Acknowledgements. AI used for **data collection, analysis, or coding → the Methods section**, naming the tool and describing how it was used.
- In one cross-journal analysis, **77.5% (31/40)** of journals examined explicitly required disclosure of AI use at submission.

**TROUT-AI (Jones, 2025)** — "Transparently Reporting Operations when Using Transformative AI." A heuristic matrix of **20 questions across 5 themes**, mapped onto **25 of 32 COREQ items** and **17 of 21 SRQR items**. Abbreviated:

| Theme | Items | What must be disclosed |
|---|---|---|
| **Research team** | T1 AI-as-researcher; T2 researcher AI literacy | Tool names + model info, tasks performed, team's competence and understanding of limitations (hallucination, bias) |
| **Participant interaction** | T3 participant contact; T4 participant knowledge; T5 participant protection | AI in recruitment/screening; AI described in informed consent; safeguards against demographic bias |
| **Study design** | T6 methodological alignment; T7 sampling; T8 policy & ethics | How AI fits the paradigm; AI's role in sampling and the selection logic; how AI was handled in IRB review |
| **Data practices** | T9 storage; T10 data creation; T11 protocol creation; T12 saturation; T13 participant checking | Where data lives and whether AI can reach it; AI transcription/synthetic data and fidelity checks; AI's role in saturation decisions and the thresholds used; whether member-checking materials were AI-generated |
| **Data analysis** | T14 coding team; T15 coding audit | AI's specific analytic role and the weight given to AI codes; a codebook annotated with **where AI contributed and all prompts used** |

**This is effectively a product spec.** Almost every TROUT-AI item is something a tool can capture automatically and emit as a formatted appendix. See avenues #25–#28.

## 3.3 Data transparency and sharing

- **Qualitative Data Repository (QDR)** at Syracuse — the dedicated archive for qualitative and multi-method data, with curation and citation standards.
- **Annotation for Transparent Inquiry (ATI)** — links specific passages in a publication to annotations containing analytic notes and excerpts from the underlying source, hosted in a repository. Successor to Active Citation; the state of the art for "show me the evidence behind this claim."
- **DA-RT** (Data Access and Research Transparency) — the push that triggered the debate; also generated substantial pushback from qualitative researchers concerned about confidentiality, context-collapse, and epistemic mismatch.

**Product implication:** ATI's model — claim → annotation → excerpt → source — is *exactly* the `code → evidence → post` chain this app already produces. Emitting an ATI-compatible or repository-ready bundle is a small step from the existing data model and a genuinely novel differentiator (avenues #28, #30).

## 3.4 Interoperability: the REFI-QDA standard

Governed by the Rotterdam Exchange Format Initiative. Two artifacts:

- **REFI-QDA Project** (`.qdpx`) — an XML-based full-project exchange file: sources, codes, coded segments, memos, variables. Supported by **ATLAS.ti (a founding member), MAXQDA, NVivo, Quirkos, f4analyse** and others.
- **REFI-QDA Codebook** (`.qdc`) — codebook-only exchange, including the code tree and memos. Supported in MAXQDA since 2018.1.

**Product implication:** this is the single highest-leverage interoperability move available. Supporting `.qdc` import/export alone would let a researcher generate a codebook here and carry it into NVivo/ATLAS.ti/MAXQDA for the rest of the analysis — turning "you must switch tools" into "this fits into your existing workflow." (Avenue #31.)

## 3.5 Ethics and transparency for social-media (Reddit) data — acutely relevant here

This app ingests Reddit `.zst` dumps into `submissions`/`comments` tables and instructs the model to quote **exact contiguous substrings** as evidence. That combination is precisely the practice the ethics literature flags.

- **Traceability is the core risk.** Reagle's empirical test found that researchers were able to locate **all verbatim quoted sources** — and many *reworded* ones — via search engines. Disguising sources works only if it is done and then *tested*.
- Recommended mitigations: paraphrasing, **vignettes** (composite/synthesized illustrations), describing rather than quoting, and analyzing threads rather than individual users.
- **IRBs are not a safety net.** Many IRBs treat public, pseudonymous data as exempt; the literature repeatedly notes that IRB guidance is *insufficient* here, because boards underestimate how easily a username or quotation can re-identify a person.
- Gliniecka's **situated ethics framework for Reddit** argues general social-media guidance does not fit Reddit specifically, given its norms of anonymity and its topic-specific communities (many of which are precisely the sensitive ones researchers want to study — mental health, addiction, abuse, and, notably for this repo's sample data, bullying).

**Product implication:** a "quote traceability checker," PII/username scrubbing, and a paraphrase/vignette generator would be *ethics infrastructure no competing tool offers*, and they map directly onto the evidence spans the app already stores. (Avenues #50–#53.)

---

# Part 4 — The evidence base on LLM-assisted qualitative coding

This is the literature that determines whether this app's core premise is defensible. The short answer: **defensible for deductive coding at scale, weaker for interpretive work, and dangerous without verification.**

## 4.1 Deductive coding: LLMs are competitive with humans

**PLOS Digital Health (2026), blinded mixed-methods comparison.** Three LLMs (GPT-5, Claude 4 Sonnet, QualiGPT) vs two human analysts on a 12,172-word focus-group transcript, against an expert adjudication panel.

- **Deductive coding:** LLMs **93.5%** agreement with the expert panel (κ = 0.34; **AC1 = 0.93**) vs humans **92.7%** (κ = 0.34; AC1 = 0.92). All LLMs non-inferior; GPT-5 and Claude 4 Sonnet reached **statistical superiority**.
- **Inductive analysis:** far more variable. Only GPT-5 achieved non-inferiority. LLMs did well on **descriptive** themes and poorly on **latent meaning, interpersonal dynamics, and affective dimensions**.
- **Hallucination taxonomy and rates:**
  - **Strict hallucination** (evidence not present in the source): **1.2%** (SD 2.1%)
  - **Expanded** (incl. misattributed speaker/researcher speech): **8.6%** (SD 5.1%)
  - **Comprehensive error rate** (incl. partial matches): **12.4%** (SD 5.1%)
- **Recommendations:** favour LLMs for high-volume descriptive coding and framework application; favour humans for deeply interpretive work; **and if using LLMs, implement quote verification, report error rates, and document how AI output entered the final analysis.**

**Deductive coding reliability study (arXiv 2507.14384).** Compared zero-shot, few-shot, definition-based, and a novel **step-by-step task decomposition** prompt on policy-domain coding. Task decomposition won: **accuracy 0.775, Cohen's κ 0.744, Krippendorff's α 0.746** — i.e. at the "substantial agreement" threshold, with stable performance across samples and good F1 in low-support classes. *Prompt architecture, not model choice, was the dominant factor.*

**LLMs in thematic analysis (arXiv 2510.18456).** Documented prompts targeting Braun & Clarke Phases 2–5, evaluated blind by four experienced researchers against rubrics derived from B&C's own quality criteria. **Evaluators preferred LLM-generated codes 61% of the time.** But the LLMs "fragmented data unnecessarily, missed latent interpretations, and sometimes produced themes with unclear boundaries."

## 4.2 What researchers actually want from AI

**"From Assistance to Autonomy" (arXiv 2501.19275).** HCI researchers were open to AI in QDA workflows but named three concerns: **data privacy, autonomy, and quality assurance**. They saw the clearest fit for AI in **pre-processing, onboarding new coders, and mediating coding conflicts** — not in making interpretive calls. The paper proposes a **spectrum from minimal to high AI involvement** rather than a single automation level.

**CoAIcoder (TOCHI).** Using a shared AI model as a *mediator between two human coders* improved efficiency and produced agreement faster in early coding — **but reduced final code diversity**. A real, measured cost of AI-mediated convergence.

**"Putting Tools in Their Place" (CSCW).** Qualitative scholars are willing to work with AI "as long as it **assists** rather than **automates** their analytic work practice."

**Related systems worth knowing:** **PaTAT** (CHI 2023) — human-AI coding via explainable interactive rule synthesis, so the researcher can see and edit the pattern the machine learned. **QualiGPT** — a GUI over ChatGPT for qualitative coding. **LOGOS** (arXiv 2509.24294) — end-to-end LLM grounded-theory: coding → semantic clustering → graph reasoning → iterative codebook refinement, with a 5-dimensional metric and a train/test split protocol, claiming ~80% alignment with expert-developed schemas across five datasets.

## 4.3 The two statistical landmines

**"LLM Hacking" (arXiv 2509.08825)** — 13 million labels across 18 LLMs. Findings:

- Roughly **31% of tested hypotheses reached an incorrect conclusion** with state-of-the-art LLMs; **~50%** with smaller models.
- Deliberate manipulation is trivially easy: **paraphrasing the prompt** can make almost any conclusion appear statistically significant.
- Findings near significance thresholds need markedly more verification.
- Mitigations catalogued: 21 techniques; **human annotations are the crucial protection against false positives**; regression correction can restore valid inference.

**Design-based Supervised Learning (Egami et al.)** — the fix for using LLM labels in downstream statistics:

- Ignoring annotation error produces **substantial bias and invalid confidence intervals** *even at 90%+ accuracy*. At 70% accuracy, coverage of a nominal 95% CI can fall to **20%**.
- The DSL procedure: (1) label everything with the LLM, (2) **randomly sample a subset for expert annotation**, (3) combine via a doubly-robust estimator to get valid estimates and CIs.

**Product implication — and possibly the single best differentiator available to this app:** the DSL workflow is *exactly* "code everything with the model, hand-verify a random subset, report corrected numbers with honest confidence intervals." The app already has the coded corpus and the sampling machinery. No CAQDAS tool on the market does this. (Avenues #19, #41.)

**Also worth noting:** inter-prompt reliability is now itself framed as a measurement problem (arXiv 2604.16413) — i.e. "what is actually being annotated" when the same construct is operationalized through different prompts. This argues for treating prompts as versioned measurement instruments, not as UI text (avenue #18).

---

# Part 5 — The competitive landscape

## 5.1 Established CAQDAS (the incumbents)

| Tool | AI features | Pricing posture | Notable limitations |
|---|---|---|---|
| **NVivo** (Lumivero) | AI Assistant add-on: multi-format & multi-language ingest, document summarization, three auto-coding modes (pattern-based, thematic, AI-suggested child codes), sentiment analysis with modifier recognition | AI Assistant **≈ $250/yr on top of base licence** | Steep learning curve; pattern-based autocoding needs substantial hand-coding first; users report crashes/data loss; time spent tidying AI output |
| **ATLAS.ti** | The most AI-invested of the three: initial code generation, hierarchy organization, multi-document analysis, conversational AI, sentiment analysis, pattern recognition ("AI Lab") | Commercial | Strong network/visual analysis; grounded-theory-friendly |
| **MAXQDA** | AI Assist add-on: summarization, coding suggestions, theme analysis, chat-with-your-data, 11 languages, GDPR compliance | AI Assist **roughly doubles** total cost | Complex UI; crash/data-loss reports |
| **Dedoose** | Keyword-based auto-coding and auto-excerpting only — "efficiency automation, not artificial intelligence" | Monthly subscription | Real-time collaboration; mixed methods |
| **Quirkos** | **Deliberately no AI.** Optional Whisper transcription add-on ($12/mo) | Modest | Founder publishes eight objections to AI in QDA: accuracy, embedded bias, lack of qualitative training data, ethical transparency, inability to grasp lived experience, speed-vs-quality, security, academic integrity |
| **Taguette** | **None.** Manual highlighting and tagging, real-time collaboration | **Free, open source** | Purely human-driven by design |
| **QualCoder** | None | Free, open source, offline | Text + images, hierarchical tags, desktop/local — poor for collaboration |
| **CATMA** | None (browser-based tagging, some visualization) | Free | Digital-humanities lineage |
| **Delve** | Chat with data, deductive codebook application, code-clarity review, **peer debriefing** support, snippet citations | Subscription | Narrower: no sentiment analysis, no automated theme discovery |

**Two things stand out.** First, every incumbent charges separately for AI, often doubling the price — a per-user-BYO-key model (as this app uses) is a genuine cost advantage. Second, the incumbents' own marketing concedes the key point: *AI tools complement but do not replace QDA software where traceability, methodological rigor, and defensible findings are required.* That sentence is the market gap this app should be aiming at.

## 5.2 AI-first UX-research repositories (the adjacent market)

**Dovetail, Hey Marvin, Looppanel, Condens, Notably, CoLoop.** These are commercially the fastest-moving segment: auto-transcription, auto-tagging, theme synthesis, nested tag structures, and traceability from insight back to the clip. Looppanel in particular markets "auto-tagging **with traceability**."

They are far ahead on **UX polish, transcription, and repository/search**, and far behind on **methodological accountability** — no IRR, no saturation, no reporting standards, no audit trail suitable for a methods section. They serve product teams, not researchers publishing in peer-reviewed venues.

**Strategic read:** this app should *not* compete with Dovetail on polish. It should compete on the axis neither the incumbents nor the UX tools occupy: **auditable, reportable, statistically-honest AI-assisted coding for academic publication.**

## 5.3 Computational social science tooling (the closest structural analogues)

- **4CAT** (Digital Methods Initiative) — modular open-source capture-and-analysis toolkit for Twitter/X, Telegram, Reddit, 4chan, 8kun, BitChute, Douban, Parler. Explicitly designed around being **transparent and traceable**, with **automatic, shareable documentation of intermediate analysis steps**. This is the closest philosophical sibling to what this app should become — and it is worth studying its provenance model directly.
- **Communalytic** — no-code CSS tool collecting and analyzing Bluesky, Mastodon, Reddit, Telegram, X, YouTube.
- **Pushshift** — the historical Reddit archive that most `.zst` dumps derive from; **Arctic Shift** is the current successor for accessible Reddit data.

These tools *acquire and describe* data well but have essentially no qualitative coding layer. This app has the coding layer and a weak acquisition layer. **Integration, not competition, is the play** (avenue #34).

## 5.4 Where this app currently sits

| Axis | This app | Best in class |
|---|---|---|
| AI-native pipeline | **Strong** — end-to-end, background jobs, model choice, map-reduce over context limits | ATLAS.ti, LOGOS |
| Cost model | **Strong** — BYO OpenRouter key, free models selectable | NVivo/MAXQDA charge $250+/yr |
| Lineage/provenance foundation | **Good** — `file_dependencies`, prompts stored per artifact | 4CAT |
| Data ingest breadth | **Weak** — Reddit `.zst` only | NVivo, 4CAT |
| Manual coding UX | **Weak** — edit-after-the-fact only | Taguette, MAXQDA |
| Rigor apparatus (IRR, saturation, verification) | **Absent** | Nobody does this well — *open territory* |
| Transparency/reporting output | **Absent** | Nobody does this well — *open territory* |
| Interoperability | **Absent** | REFI-QDA members |
| Collaboration | **Absent** — single-owner | Dedoose, Delve, Taguette |
| Analysis/visualization | **Minimal** — code frequency only | MAXQDA, NVivo |

---

# Part 6 — Gap analysis of the application as it stands

Grounded in the actual code, not the docs. Each row is a *verified* observation. Gap IDs are prefixed `GAP-` to keep them distinct from the Theme G avenue numbers in Part 7.

| # | Observation | Where | Why it matters methodologically |
|---|---|---|---|
| GAP-1 | **Evidence spans are never verified.** The prompt instructs "EVIDENCE snippets must be exact contiguous substrings," but nothing checks it. | `backend/scripts/codebook_apply.py:311`; no check in `coding_service.py` | The PLOS study measured 1.2%–12.4% error rates and named quote verification as a required practice. This is free to implement and currently missing. |
| GAP-2 | **Code names are never validated against the codebook.** The prompt says "use only exact code names," unenforced. | `codebook_apply.py` parse path | An invented code silently becomes a real row in `coding_entries` and then flows into frequency counts and summaries. |
| GAP-3 | **POST_IDs are not validated against the source.** | same | Same failure mode; a hallucinated ID produces an uncheckable coded row. |
| GAP-4 | **No character offsets.** Evidence is stored as free text. | `storage_models.py::CodingEntry` | Prevents highlighting in source, overlap detection, co-occurrence by proximity, and segment-level IRR. |
| GAP-5 | **`CodingEntry` PK is `(file_id, post_id, code)`.** | `storage_models.py` | A post cannot carry the same code twice (two distinct excerpts → one row), and there is no room for **coder identity** — which structurally blocks double-coding and IRR. |
| GAP-6 | **The model used is not persisted on the artifact.** `File` stores `systemprompt`/`userprompt` but no model, temperature, or sample size; those live only in `jobs.payload`, with no FK from `files` back to the job. | `database.py::File`, `jobs/models.py::Job` | Model + version is a mandatory disclosure under every AI-reporting guideline. Right now a codebook cannot say which model made it. |
| GAP-7 | **Sampling is `ORDER BY RANDOM() LIMIT n` only.** | `repositories/raw_data_repo.py` (per `documentation/concepts.md`) | Qualitative sampling is purposive/theoretical/maximum-variation. Random sampling is a *quantitative* logic and is a reportable weakness under TROUT-AI T7. |
| GAP-8 | **No export of any kind.** No CSV, XLSX, JSON, QDPX, or report. | no export endpoints anywhere in `backend/app/api/` | Data is trapped. Blocks archiving, statistics, co-authorship, and the entire REFI-QDA interop story. |
| GAP-9 | **Single-owner data model.** Every `File`/`Project` has `user_id`; no sharing, roles, or teams. | `database.py` | Qualitative coding is overwhelmingly team-based. Also blocks peer debriefing and IRR by construction. |
| GAP-10 | **No memos, no reflexivity notes, no decision log.** | — | Directly blocks *dependability* and *confirmability*, two of Lincoln & Guba's four criteria. |
| GAP-11 | **Comparison outputs are LLM prose, not computed metrics.** | `codebook_service.py:436`, `coding_service.py` | "Compare codings" is the natural home for κ/α/AC1 and a confusion matrix; instead it returns an essay with a self-assessed "confidence level." |
| GAP-12 | **Codebook lacks exclusion criteria** ("when *not* to use this code") and the brief/full definition split. | `codebook_generator.py::_GENERATE_SYSTEM_PROMPT` | MacQueen's six-component structure; exclusion criteria are the highest-yield component for agreement. |
| GAP-13 | **Second-cycle coding is absent.** The pipeline ends at codes → prose summary. | whole pipeline | Codes are not themes. Under Braun & Clarke this means the tool supports Phase 2 and skips Phases 3–5. |
| GAP-14 | **Only one coding pass per artifact; no versioning of a codebook under revision.** Edits overwrite via `save-file-codebook`. | `codebook_routes.py` | Codebook development is iterative; the revision history *is* the audit trail. |
| GAP-15 | **Reddit-only ingest** (`.zst` → `submissions`/`comments`). | `storage_models.py` | Excludes interviews, focus groups, open-ended survey items, documents — i.e. most of the qualitative research market. |
| GAP-16 | **In-flight jobs are lost on restart** (API key held only in the runner's closure). | `jobs/service.py` (documented trade-off) | An acknowledged trade-off, but a multi-hour coding run over a large corpus is exactly what users will submit. |
| GAP-17 | **Module-level model constants are not rebound by the daily catalog refresh.** | `ai_models.py` / `codebook_generator.py` (documented) | Means "the default model" can drift between what's documented and what ran — a reproducibility hazard given §4.3. |
| GAP-18 | **No PII handling or quote-traceability protection**, on a corpus of Reddit posts including sensitive communities (the repo's own sample is `bullying submissions.zst`). | ingest path | The ethics literature's central concern, unmitigated. |

**Fair summary:** the *engineering* is well ahead of the *methodology*. The architecture (artifact lineage, background jobs, repository layer, structured `coding_entries`, prompt persistence) is a genuinely good foundation for exactly the features that are missing. Most of what follows is additive, not a rewrite.

---

# Part 7 — Expansion avenues

**96 avenues, in nine themes.** Each: what it is, why the literature demands it, where it lands in this codebase, and effort/impact.

## Theme A — Methodological depth: become a real QDA tool, not a coding script

**A1. Second-cycle coding as a first-class artifact.** ★★★★★ · **L**
Add a `theme` artifact type: codes → categories → themes, with each theme carrying constituent codes, a definition, boundary conditions, and exemplar quotes. This is Braun & Clarke Phases 3–5 and Saldaña's Second Cycle. *Where:* new `file_type`, new service, `file_dependencies` already models the parent link. Reuses the map-reduce consolidation pattern already in `generate_codebook_map_reduce`.

**A2. Directed/deductive mode — bring your own codebook.** ★★★★★ · **S**
Let users **import** an existing published codebook (paste markdown, upload CSV, or REFI-QDA `.qdc`) and apply it without generating one. This is Hsieh & Shannon's *directed* content analysis and is the workflow where LLMs demonstrably match human coders (93.5% vs 92.7%). *Where:* `ApplyCodebookPanel.jsx` already accepts a codebook by file id; add an "import codebook" path into `artifact_content`. Lowest-effort/highest-credibility item on this list.

**A3. Framework matrix view (cases × themes).** ★★★★ · **M**
The Gale et al. charting step. Rows = cases (post, author, subreddit, or an imported participant id), columns = codes/themes, cells = the coded excerpts, with drill-down. *Where:* pure read-model over `coding_entries` joined to `submissions`; a new repo function plus a new page.

**A4. Iterative/theoretical sampling loop.** ★★★★ · **M**
Instead of one batch: code a sample → show what's new → let the researcher choose the *next* sample (more of subreddit X, longer posts, posts unmatched by any code) → code again, accumulating into the same artifact. This is constant comparison, and it makes grounded theory possible at all. *Where:* `coding_service` + an "extend coding" job type; `coding_entries` is already keyed to allow appends.

**A5. Analytic memos everywhere.** ★★★★★ · **M**
A `memo` table attached polymorphically to a project, artifact, code, or individual coded segment, with timestamps and authorship. Saldaña treats memoing as part of the method; Lincoln & Guba's dependability depends on it. *Where:* new table + Alembic revision; UI hooks in `ViewCodebook` and `ViewCoding`.

**A6. Reflexivity / positionality statement per project.** ★★★ · **S**
A structured field on `Project`, prompted at creation, that flows into the generated methods appendix. Under TROUT-AI, reflexivity now explicitly extends to *the technological* dimension — which tools, which models, what the team understands about their limits.

**A7. Negative case analysis.** ★★★★ · **M**
"Find data that contradicts this code/theme." Two implementations, both cheap: (a) surface all posts that received *no* code — the tool discards these silently today, and they are analytically the most interesting; (b) an explicit LLM pass asking for disconfirming evidence for a named theme. *Where:* `coding_repo` anti-join against `submissions`.

**A8. Saturation tracking and reporting.** ★★★★★ · **M**
Because coding runs in batches (`context_window.batch_by_separator`), the app can record **new codes per batch** for free and plot the accumulation curve, distinguishing **code saturation** ("no new codes") from **meaning saturation** ("no new dimensions of existing codes"). Output: a chart plus a sentence for the methods section. Nobody in the market does this; it converts an arbitrary `sample_percentage` slider into a defensible stopping rule.

**A9. Purposive, stratified, and maximum-variation sampling.** ★★★★ · **M**
Replace/augment `ORDER BY RANDOM()`: stratify by subreddit, time window, score, word count, thread depth, or author; maximum-variation sampling via embedding diversity; extreme/deviant case sampling. Record the strategy on the artifact for TROUT-AI T7 disclosure. *Where:* `raw_data_repo`, plus fields on the filter/apply forms.

**A10. Codebook versioning with diffs.** ★★★★ · **M**
Every save creates a version; show a structural diff (codes added/removed/renamed/redefined) rather than a text diff; allow rollback. The revision history is the audit trail for codebook development. *Where:* `artifact_content` is keyed by `file_id` only — add a version column + Alembic revision.

**A11. MacQueen-complete code structure.** ★★★★ · **S**
Add **brief definition**, **full definition** and **exclusion criteria ("when NOT to use")** to the generator prompt, the parser (`parse_codebook_to_json`), the editor, and the apply prompt. Exclusion criteria measurably improve agreement. *Where:* `_GENERATE_SYSTEM_PROMPT`, `_CONSOLIDATE_SYSTEM_PROMPT`, and the codebook parser. Genuinely a day's work.

**A12. Conversation-aware coding.** ★★★ · **M**
`comments` carries `link_id`/`parent_id` but coding treats posts as isolated units. Code threads with parent context; code at the comment level with the submission as context. Reddit meaning is frequently interactional, and the ethics literature *recommends* analyzing threads rather than individuals.

**A13. In-vivo coding mode.** ★★ · **S**
A first-cycle method where codes are participants' own words verbatim. Trivial as a prompt variant, and it visibly signals methodological literacy.

**A14. Method-guided workflows.** ★★★★ · **M**
A project-creation step: "Which tradition? Reflexive TA / grounded theory / content analysis / framework method." The choice then configures the pipeline — which prompts, whether IRR is offered (it should be suppressed for reflexive TA), which stages appear, which reporting template is generated. This is how the tool stops being method-agnostic mush and starts being defensible.

**A15. Code hierarchy / code tree.** ★★★ · **M**
Currently two levels (family → code), flat text. Real codebooks nest arbitrarily deep, and REFI-QDA models a code *tree*. Needed for `.qdc` fidelity anyway.

## Theme B — Rigor and validation: the biggest open territory

**B1. Evidence-span verification.** ★★★★★ · **S** — *the single highest value-to-effort item in this document*
On parse, check every evidence snippet against the source text. Classify per the PLOS taxonomy: **exact match / partial match / strict hallucination / misattribution**. Store the verdict and the character offsets. Show verified quotes in green, partial in amber, unverifiable in red. Report the rate. *Where:* `codebook_apply.py::_extract_structured_records` already isolates the snippets; add `evidence_start`/`evidence_end`/`match_type` columns to `CodingEntry` + an Alembic revision. This directly implements the PLOS recommendation and turns a known 1.2–12.4% error rate into a *measured, displayed* number.

**B2. Code-name validation against the codebook.** ★★★★ · **S**
Reject or flag codes not present in the codebook; offer fuzzy-match repair ("did the model mean *Peer Exclusion*?"). *Where:* same parse path; the codebook is already parseable into structured codes via `parse_codebook_to_json`.

**B3. Post-ID validation.** ★★★ · **S**
Drop or flag coded rows whose `post_id` is not in the source sample.

**B4. Coder identity on every coded segment.** ★★★★★ · **M** — *prerequisite for most of Theme B*
Change `CodingEntry`'s key to include a `coder` (`ai:<model>@<version>` or `user:<id>`) and allow multiple excerpts per (post, code). Without this, double-coding and IRR are structurally impossible. *Where:* `storage_models.py` + Alembic; the PK change ripples into `coding_repo` and `bulk_insert_coding_entries`.

**B5. Human adjudication queue.** ★★★★★ · **L**
A focused review UI: one segment at a time, showing the post, the AI's code, the AI's evidence highlighted in context, and the code's definition — with accept / reject / recode / add-memo. Keyboard-driven. This is the interaction the entire literature converges on ("assist, don't automate") and the app currently has nothing like it.

**B6. Blind double-coding workflow.** ★★★★ · **M**
Assign a random 10–25% subset to a second coder (human or a different model) with the first coder's decisions hidden, then reconcile. Implements O'Connor & Joffe's concrete guidance.

**B7. Inter-coder reliability metrics.** ★★★★★ · **M**
Percent agreement, Cohen's **κ**, Krippendorff's **α**, Fleiss' κ, and **Gwet's AC1** — computed over human–human, human–AI, and AI–AI pairs. Report all of them with an explanation of the kappa paradox (κ = 0.34 alongside AC1 = 0.93 on the same data is the canonical illustration). Show a per-code agreement table so users can see *which* codes are unreliable. *Where:* pure computation over `coding_entries` once B4 lands; a new `services/reliability_service.py`. **This is what "Compare Codings" should have been.**

**B8. Multi-model ensemble coding.** ★★★★★ · **M**
The app *already* lets users choose among many OpenRouter models. Run the same codebook through 2–3 models, keep unanimous codes, and route disagreements to human review. This is triangulation by analyst, mechanized — and it is a capability the incumbents (locked to one vendor's AI) cannot easily match. *Where:* a new job type that fans out over `chat_completion`; the `context_window` budgeting already generalizes per model.

**B9. Prompt-sensitivity / robustness analysis.** ★★★★ · **M**
Run the same coding task under N paraphrased prompts and report label stability. This measures *inter-prompt reliability* and is the direct defence against LLM hacking, where "paraphrasing prompts can make nearly any conclusion appear significant." Treat prompts as versioned measurement instruments — the `prompts` table already exists for the storage half of this.

**B10. Test–retest stability.** ★★★ · **S**
Re-run the identical prompt/model/data and report the proportion of identical decisions. Cheap, and it gives users a number for non-determinism.

**B11. Gold-standard validation sets.** ★★★★ · **M**
Let a user mark a hand-coded subset as gold, then score any AI run against it: accuracy, per-code precision/recall/F1, κ/α/AC1. Persist as a validation artifact linked by `file_dependencies`.

**B12. DSL / prediction-powered inference for downstream statistics.** ★★★★★ · **L** — *the most defensible differentiator available*
Implement the Egami et al. workflow: LLM-code everything → randomly sample for expert annotation → doubly-robust estimation → report prevalence, subgroup differences, and trends **with valid confidence intervals**. This converts "the model says 34% of posts express X" (which is not a defensible claim) into "34% [95% CI 29–39%], corrected for classifier error against 200 human-verified cases" (which is publishable). *Where:* builds on B11; the statistics are a contained numeric module.

**B13. Per-decision confidence and abstention.** ★★★ · **M**
Ask the model for a confidence rating (or use logprobs where the provider exposes them), store it, and let low-confidence decisions route automatically into the adjudication queue (B5). Cheap targeting of scarce human attention.

**B14. Deterministic replay.** ★★★★ · **M**
Pin model **snapshot** ids (not floating aliases), record temperature/seed/parameters, hash the prompt, and store all of it on the artifact. Also resolves GAP-17: bind model constants at call time. Without this the tool cannot honestly claim reproducibility.

**B15. Coding-decision provenance chain.** ★★★★ · **M**
For every coded segment: which model, which prompt version, which batch, which codebook version, which raw API response. Confirmability in Lincoln & Guba's sense is precisely this chain.

**B16. Built-in evaluation harness.** ★★★ · **M**
Fixture corpora with expert codings, run in CI, tracking agreement over time so prompt changes are evaluated rather than vibed. The test layout in `tests/backend/` already mirrors the package structure; this slots in.

**B17. Bias and coverage checks.** ★★★ · **M**
Report whether coding density varies systematically by post length, score, subreddit, or time — a proxy for whether the model is under-coding some voices. LLM annotation error is well documented to be **non-random**, which is exactly why DSL exists.

**B18. "Uncoded residue" report.** ★★★★ · **S**
What proportion of sampled posts received no codes at all, and what do they look like? Today they vanish. High rates of uncoded data mean the codebook doesn't fit — a critical, currently invisible signal, and a natural entry point to negative case analysis (A7).

## Theme C — Transparency and reporting: turn compliance into a feature

**C1. Automatic audit trail.** ★★★★★ · **M**
An append-only, timestamped `decision_log` per project: artifact created, prompt used, model used, sample drawn, codebook edited (with the diff), coding accepted/rejected, memo written. Rendered as a readable, exportable trail. This *is* Lincoln & Guba dependability, and the entire architecture (jobs, artifacts, dependencies) already emits these events — they're just not captured.

**C2. One-click methods appendix.** ★★★★★ · **M**
Generate a draft Methods section: data source and date range, sampling strategy and n, model + version, verbatim system and user prompts, codebook version, IRR statistics, saturation curve, verification rates, human adjudication rates. Populate a **COREQ (32-item)** or **SRQR (21-item)** checklist with what the tool knows and mark the rest for the user. Enormous time-saver, and it makes rigor legible to reviewers.

**C3. TROUT-AI disclosure generator.** ★★★★★ · **M**
Walk the 20 questions across the 5 themes, pre-answering everything the system knows (T1 roles, T7 sampling logic, T9 storage, T12 saturation, T14 AI's coding role, T15 the full prompt log) and prompting the researcher for the rest (T2 AI literacy, T8 IRB discussion). Output a submission-ready disclosure block. **No competing tool does this. It is a defensible product wedge, and the framework maps to 25/32 COREQ and 17/21 SRQR items.**

**C4. AI disclosure statement for journals.** ★★★★ · **S**
A short COPE/ICMJE-compliant paragraph naming tool, model, version and tasks, correctly targeted at the **Methods** section (analysis/coding) rather than Acknowledgements (writing).

**C5. Full run provenance on every artifact.** ★★★★★ · **S**
Fix GAP-6: persist model id, model version, temperature, sample strategy, sample size, token counts, cost, and a `job_id` FK on `File`. Small schema change, and everything in Theme C depends on it.

**C6. Interactive lineage/provenance graph.** ★★★ · **M**
`file_dependencies` already stores the DAG; render it. Click any node to see the prompts, model and parameters that produced it. 4CAT's traceability model is the reference implementation to study.

**C7. Reproducibility bundle export.** ★★★★ · **M**
A single archive: source data (or a hash + acquisition recipe if redistribution is barred), codebook versions, all prompts, all model settings, coded output, memos, audit trail, and a `manifest.json`. Depositable in **QDR**, OSF, or Zenodo, with a citable DOI.

**C8. ATI-style annotated evidence export.** ★★★★ · **M**
Claim → annotation → excerpt → source. This is *precisely* the `code → evidence → post_id` chain already in `coding_entries` (and becomes exact once B1 adds offsets). Export as ATI-compatible annotations so reviewers can click a claim and land on the underlying data. Novel; nobody offers it.

**C9. Shareable read-only artifact links.** ★★★ · **M**
Peer debriefing and reviewer access without an account. Delve markets peer debriefing as a headline feature; this is the minimal version.

**C10. Prompt library with versioning.** ★★★ · **S**
The `prompts` table and `PromptManager.jsx` already exist — extend to immutable versions, hashes, and "which artifacts used this prompt version." Required by TROUT-AI T15 ("including any and all prompts") and by B9.

**C11. Cost and token accounting.** ★★★ · **S**
Per job, per project, cumulative. Researchers write grant budgets; "this coding run cost $4.12 across 71,000 tokens" is genuinely useful and also a reportable methods detail.

## Theme D — Interoperability and data ingest: stop being an island

**D1. REFI-QDA Codebook (`.qdc`) import/export.** ★★★★★ · **M**
Round-trip codebooks with NVivo, ATLAS.ti, MAXQDA, Quirkos, f4analyse. Changes the pitch from "switch to us" to "generate your codebook here in ten minutes, then continue in NVivo." Depends on A15 (code tree). **Best single interoperability investment.**

**D2. REFI-QDA Project (`.qdpx`) export.** ★★★★ · **L**
Full project exchange — sources, codes, coded segments, memos, variables. Requires character offsets (B1) and memos (A5), so it naturally sequences after them.

**D3. Plain tabular exports.** ★★★★★ · **S**
CSV/XLSX/JSON of coded segments, code frequencies, and codebooks. Fixes GAP-8, unblocks R/Python/SPSS analysis, and takes an afternoon. There is no defensible reason this is missing.

**D4. Generic text ingest.** ★★★★★ · **L**
Interview transcripts, focus groups, open-ended survey responses, field notes, documents (PDF/DOCX/TXT), and generic CSV with a column mapper. **This is the biggest market-size lever in the document** — the entire CAQDAS market is interviews, and the app currently cannot touch it. *Where:* a `documents`/`text_units` table alongside `submissions`/`comments`, with the coding pipeline generalized over a "unit of analysis" abstraction rather than a Reddit post.

**D5. Additional social platforms.** ★★★ · **L**
X/Bluesky/Mastodon/YouTube/Telegram — or, far cheaper, **import from 4CAT and Communalytic exports** rather than building collectors. Let the CSS tools do acquisition; do coding.

**D6. Arctic Shift / modern Reddit acquisition.** ★★★ · **M**
Pushshift's public service is gone; Arctic Shift is the current successor. In-app acquisition (subreddit, date range, query) beats "find a `.zst` somewhere," and it lets the tool record acquisition parameters as provenance.

**D7. Audio/video with transcription.** ★★★ · **L**
Whisper-based transcription with timestamps, so codes anchor to time offsets. Quirkos sells exactly this at $12/month; the UX-research tools treat it as table stakes.

**D8. Multilingual coding.** ★★★ · **M**
Code in the source language, with optional translation whose provenance is recorded (MAXQDA advertises 11 languages). Important for non-Anglophone research and a real market beyond the US/UK.

**D9. Public API + Python client.** ★★★ · **M**
The backend is already a clean REST API. A documented API and a thin notebook client makes the tool scriptable for computational researchers — the population most likely to code 100k posts.

**D10. Import an existing hand-coded dataset.** ★★★★ · **S**
Upload a CSV of human codings to serve as the gold standard (B11) or as coder A in an IRR comparison. Instant credibility path for a sceptical researcher: "show me it agrees with what I already did."

## Theme E — Analysis and visualization: make the coded data answer questions

**E1. Code frequency and distribution dashboard.** ★★★★ · **S**
`coding_repo.code_frequency` already exists and is used only to feed a summarization prompt. Surface it: counts, share of corpus, codes-per-post distribution, code family rollups.

**E2. Code co-occurrence matrix and network.** ★★★★ · **M**
Which codes appear together on the same post/thread? MAXQDA's Code Relations Browser is the reference. Pure SQL self-join on `coding_entries`; with offsets (B1) you also get proximity- and overlap-based co-occurrence.

**E3. Crosstabs by attribute.** ★★★★ · **M**
Code × subreddit, code × time window, code × score bucket, code × author-type. This is the mixed-methods bridge and is exactly what `submissions`' columns are for. NVivo's crosstab/matrix query is the reference.

**E4. Temporal trend analysis.** ★★★ · **M**
`created_utc` is already stored. Code prevalence over time, with change-point detection. Reddit corpora are longitudinal by nature and this is currently thrown away.

**E5. Quantitizing with honest error bars.** ★★★★ · **M**
Summative content analysis (Hsieh & Shannon) done properly: counts and proportions, but corrected via B12 rather than reported raw.

**E6. Quote bank / evidence explorer.** ★★★★ · **M**
Browse every excerpt for a code, expand to full post context, jump to the thread, filter by verification status, star for the write-up. This is the artifact researchers actually need when drafting a paper, and it's a short hop from existing data.

**E7. Full-text and boolean search over coded segments.** ★★★ · **M**
Postgres full-text search across submissions, comments and evidence, with code filters. Basic CAQDAS retrieval; currently absent.

**E8. Semantic search and embedding-based exploration.** ★★★ · **L**
Pre-coding familiarization (Braun & Clarke Phase 1, which the app skips entirely): cluster the corpus, surface exemplars and outliers, let researchers *read before coding*. A LLooM/PaTAT-style concept-induction view fits here.

**E9. Code-density heatmap over the corpus.** ★★ · **S**
Which regions of the data are heavily coded and which are barren — a fast visual diagnostic for codebook fit, complementary to B18.

**E10. Codebook comparison as computed diff, not prose.** ★★★★ · **S**
Replace/augment `compare_codebooks`' essay with a structural comparison: codes only in A, only in B, matched by name, matched semantically, definitional divergence — with the LLM used only for the semantic matching, not for the whole judgment. More useful *and* cheaper.

## Theme F — Collaboration: qualitative research is a team sport

**F1. Teams and shared projects with roles.** ★★★★★ · **L**
Owner / analyst / reviewer / read-only. Everything in Theme B (double-coding, IRR, adjudication) and C9 (peer debriefing) depends on this. *Where:* the single-`user_id` ownership model in `database.py` is the blocker; a `project_members` table plus authorization changes in `require_user_id` call sites.

**F2. Coding assignment and workload tracking.** ★★★ · **M**
Assign segments to coders, track progress, flag the double-coded subset.

**F3. Threaded discussion on codes and disagreements.** ★★★ · **M**
Where reconciliation actually happens. Preserve it — the disagreement record is itself audit-trail material.

**F4. Structured peer-debriefing mode.** ★★★ · **M**
An outsider gets read-only access plus a prompt list ("what would a sceptic say about this theme?"). Delve ships a version of this; it's cheap and it maps to a named credibility technique.

**F5. Coder training and calibration.** ★★★ · **M**
New coders code a calibration set, get scored against the gold standard, and see where they diverge. The "AI for onboarding new coders" use case researchers themselves nominated in arXiv 2501.19275.

**F6. Shared codebook library.** ★★★ · **M**
Publish and reuse validated codebooks across projects and, optionally, across users — with citation. Directed content analysis (A2) needs a supply of codebooks; this creates one.

## Theme G — Ethics and compliance: the unclaimed high ground

**G1. PII detection and redaction at ingest.** ★★★★ · **M**
Usernames, real names, locations, handles, URLs, emails. Store the mapping separately so the analysis stays coherent while the working corpus is de-identified.

**G2. Quote traceability checker.** ★★★★★ · **M** — *novel; nobody offers it*
Before a quote goes into a paper, flag whether it is verbatim (and therefore search-engine locatable — the empirical finding is that **all** verbatim quotes and many reworded ones were found). Offer graduated protections: paraphrase, generalize, or synthesize a composite **vignette**, each labelled as such in the export. This makes a documented ethical failure mode into a one-click safeguard.

**G3. Sensitive-community warnings.** ★★★ · **S**
Flag when the corpus comes from communities where the situated-ethics literature counsels extra care (mental health, self-harm, addiction, abuse, minors — the repo's own sample is `bullying submissions.zst`), and link the relevant guidance.

**G4. IRB/ethics documentation helper.** ★★★ · **M**
Generate a data-handling description for an ethics application: what data, from where, where stored, which third parties see it (OpenRouter!), retention, de-identification. TROUT-AI T8/T9 make this a disclosure requirement, and most researchers do not realize their corpus is being sent to a third-party inference provider.

**G5. Local / self-hosted model support.** ★★★★★ · **L**
Ollama, vLLM, or any OpenAI-compatible endpoint, plus a configurable base URL. **This is a hard gate, not a nice-to-have:** many IRBs and most GDPR-governed institutions forbid sending participant data to a commercial API, and "data privacy" was the first concern researchers named. *Where:* `external/openrouter_client.py` is already the single external-call seam — this is a genuinely contained change, and the architecture deserves credit for that.

**G6. Data retention, deletion, and encryption policy.** ★★★ · **M**
Per-project retention windows, hard delete, encryption at rest. TROUT-AI T9.

**G7. Consent and terms-of-use provenance.** ★★ · **S**
Record how the data was obtained, under what platform terms, and whether an ethics approval reference exists. Travels with the reproducibility bundle.

**G8. Model/provider data-use transparency.** ★★★ · **S**
Show, per selected model, whether the provider trains on submitted data (OpenRouter exposes much of this). Free models are frequently the *least* privacy-preserving — and this app defaults to free models.

## Theme H — Positioning, market, and adjacent applications

**H1. Target academic qualitative researchers explicitly.** ★★★★★ · **S**
The market gap is unambiguous: incumbents have rigor infrastructure but bolted-on AI at $250+/yr; UX-research tools have great AI but no methodological accountability. **Auditable, reportable, statistically-honest AI-assisted coding** is unoccupied. Everything in Themes B and C serves this position.

**H2. Teaching mode.** ★★★★ · **M**
Methods courses need exactly this: a scaffolded environment where students code, compare against an instructor's gold standard, see their κ/α, and read the audit trail of their own decisions. Institutional sales follow teaching adoption; NVivo's academic dominance was built this way.

**H3. Qualitative evidence synthesis / systematic review screening.** ★★★ · **L**
Title/abstract screening and thematic synthesis are structurally identical to filter → codebook → apply. ENTREQ is the reporting standard. Large adjacent market, minimal new machinery.

**H4. Policy consultation and open-response analysis.** ★★★★ · **M**
Government consultations, citizen assemblies, open-ended survey items — tens of thousands of free-text responses that must be coded *and* defended publicly. This is arguably a better product-market fit than academia: same rigor demands, more budget, less tool lock-in. Depends on D4.

**H5. Content-moderation and trust-and-safety research.** ★★★ · **M**
Reddit-native ingest is already an advantage here. Codebooks are policy taxonomies; IRR is already standard practice in that field.

**H6. Market/consumer research and support-ticket analysis.** ★★★ · **M**
The Dovetail segment. Lower rigor demands, higher willingness to pay, but a crowded and well-funded field — pursue only as a secondary revenue line.

**H7. Institutional/campus deployment.** ★★★★ · **L**
Self-hosted (G5) + teams (F1) + SSO = a site licence. This is how CAQDAS is actually purchased — libraries and departments, not individuals.

**H8. Open-source the core, monetize hosting/institutional features.** ★★★ · **M**
Taguette, QualCoder and CATMA prove the demand for free and open QDA; none has credible AI. An open core with paid hosting, collaboration and compliance features is a viable and credibility-generating path, especially for academic adoption.

**H9. Publish a validation study of the tool itself.** ★★★★★ · **M**
Run the app's pipeline against a published human-coded dataset and report agreement, hallucination rates and DSL-corrected estimates — the design used by the PLOS study. A citable validation paper is *the* adoption currency in academia and turns every rigor feature into evidence rather than marketing.

**H10. Ship prompts as citable, versioned methods artifacts.** ★★★ · **S**
Publish the system prompts publicly with version numbers and a DOI so papers can cite "Codebook Generator prompt v2.1." Cheap, and it converts GAP-17-style drift into a managed public contract.

## Theme I — Platform work that unblocks the rest

**I1. Durable job execution.** ★★★★ · **M**
Today an in-flight job dies with the process because the API key lives only in the runner's closure. Options: an encrypted at-rest key with a short TTL, a session-scoped secret store, or a worker process with its own credential. Multi-hour coding runs over 100k posts make this a correctness issue, not an optimization.

**I2. Resumable and idempotent batch coding.** ★★★★ · **M**
Checkpoint per batch so a failure resumes rather than restarts. `ProgressTracker` already tracks batch progress — persist the completed batches too.

**I3. LLM response caching and deduplication.** ★★★ · **M**
Cache on (model, prompt hash, params). Cuts cost, and makes re-running an analysis for reproducibility nearly free.

**I4. Model pinning and catalog snapshots.** ★★★★ · **S**
Fixes GAP-17: bind model constants at call time, store the catalog snapshot per run, and warn when a previously used model disappears from the catalog. Reproducibility depends on this.

**I5. Rate-limit and quota handling with clear user feedback.** ★★★ · **S**
Free OpenRouter models are frequently overloaded; the retry path already exists but the failure semantics of a *partially* coded corpus need to be explicit.

**I6. Batch-size and cost estimation before submitting.** ★★★ · **S**
`context_window.max_prompt_chars` already computes the batching; show the user "this will be 14 calls, ~$0.90, ~6 minutes" before they commit.

**I7. Structured outputs instead of a bespoke DSL.** ★★★★ · **M**
`codebook_apply.py` carries ~150 lines of regex to parse a `POST_ID/CODE/EVIDENCE` text format, with fallbacks for bullets, fences, headers and smart quotes. Provider-side JSON schema / structured outputs would eliminate most of that parser and most malformed-output failures. Keep the regex path as a fallback for models that don't support it.

**I8. Streaming progress with partial results.** ★★ · **M**
Show coded posts as they arrive rather than at the end of a long run. `ProgressTracker` and the polling infrastructure are already in place.

---

# Part 8 — Synthesis: what to build, in what order

## 8.1 The ten highest-leverage bets

Ranked by (methodological credibility gained) × (evidence in the literature) ÷ (effort), with dependencies noted.

| Rank | Avenue | Why it wins |
|---|---|---|
| 1 | **B1 — Evidence-span verification** | Days of work. Directly implements the PLOS recommendation. Turns an invisible 1.2–12.4% error rate into a displayed, reportable number. Unblocks offsets, highlighting, co-occurrence, and QDPX export. |
| 2 | **C5 + C1 — Full run provenance and the audit trail** | Small schema change; everything in Theme C depends on it. Delivers Lincoln & Guba's dependability and confirmability, the two criteria that are pure software. |
| 3 | **B4 + B7 — Coder identity and real IRR metrics** | Converts the "Compare Codings" essay into κ/α/AC1 with per-code breakdown. This is the number reviewers ask for. |
| 4 | **D3 — Tabular export** | An afternoon's work removing an indefensible blocker. Nothing else in Theme E or the statistics story matters if data can't leave. |
| 5 | **A2 — Directed/deductive mode (bring your own codebook)** | The workflow where LLMs *provably* match human coders. Small change; large credibility gain; opens the health/policy market. |
| 6 | **C3 + C2 — TROUT-AI disclosure and the methods appendix** | Nobody offers this. It maps to 25/32 COREQ and 17/21 SRQR items and saves researchers hours. A defensible product wedge. |
| 7 | **B5 — Human adjudication queue** | The interaction the entire literature converges on: assist, don't automate. Currently the app's most conspicuous absence. |
| 8 | **G5 — Local/self-hosted model support** | A hard gate for IRB- and GDPR-constrained researchers. The single external-call seam makes it a contained change. |
| 9 | **D1 — REFI-QDA codebook interop** | Turns "switch to us" into "fits your workflow." Best interoperability return available. |
| 10 | **B12 — DSL-corrected estimates** | The most genuinely novel capability on the list. Makes quantitative claims from AI-coded data *publishable*. Needs B11 first. |

**Two honourable mentions with unusual upside:** **A8 (saturation tracking)** — nearly free given batch coding, and no competitor does it; **G2 (quote traceability checker)** — addresses a documented ethical failure with no market equivalent, and it is directly on-point for a Reddit-based tool.

## 8.2 A phased sequence

**Phase 1 — "Trustworthy output" (≈ 4–6 weeks).** *Goal: every number the tool shows can be checked.*
B1 (span verification) → B2, B3 (code/ID validation) → B18 (uncoded residue) → C5 (run provenance) → D3 (export) → E1 (frequency dashboard) → I4 (model pinning).
*Outcome:* the app stops being a black box. Every coded row is verifiable, every artifact says what made it, and the data can leave.

**Phase 2 — "Defensible method" (≈ 6–10 weeks).** *Goal: a methods section can be written from the tool's output.*
B4 (coder identity) → B5 (adjudication queue) → B6/B7 (double-coding + IRR) → A5 (memos) → C1 (audit trail) → A8 (saturation) → A11 (MacQueen-complete codebook) → A2 (directed mode).
*Outcome:* the tool supports the full rigor apparatus for codebook-based analysis, with a human in the loop by design.

**Phase 3 — "Publishable and portable" (≈ 8–12 weeks).**
C2 (methods appendix) → C3 (TROUT-AI) → C4 (AI disclosure) → D1 (`.qdc`) → C7 (repro bundle) → B11 (gold sets) → B12 (DSL) → G5 (local models).
*Outcome:* output that clears journal review, and interoperability with the tools reviewers' co-authors already use.

**Phase 4 — "Team and scale."**
F1 (teams) → F2–F5 (assignment, discussion, debriefing, calibration) → I1/I2 (durable, resumable jobs) → A1 (second-cycle themes) → E2/E3 (co-occurrence, crosstabs).

**Phase 5 — "New markets."**
D4 (generic text ingest — the biggest market lever) → H4 (policy consultations) → H2 (teaching) → H7 (institutional deployment) → H9 (publish a validation study).

## 8.3 The strategic thesis in one paragraph

The AI qualitative-analysis market is splitting into tools that are **methodologically credible but weakly AI-enabled** (NVivo, ATLAS.ti, MAXQDA — bolt-on AI at a punitive price) and tools that are **strongly AI-enabled but methodologically illiterate** (Dovetail, Marvin, Looppanel — no IRR, no saturation, no audit trail, no reporting standard). Meanwhile the research literature has, in the last two years, converged on a very specific and *implementable* set of requirements: verify quotes, report error rates, disclose models and prompts, keep a human adjudicating, correct your statistics for classifier error, and document everything against COREQ/SRQR/TROUT-AI. **Nobody is building the tool that does those things by default.** This application already has the pipeline, the artifact lineage, the multi-model access and the structured coding store needed to be that tool. The gap is not architectural; it is a specific, enumerable set of features — and most of the highest-value ones (B1, C5, D3, B7) are days-to-weeks of work, not quarters.

## 8.4 What *not* to build

- **Don't chase Dovetail on transcription/repository polish.** Well-funded, crowded, and orthogonal to the defensible advantage.
- **Don't add more free-form LLM prose outputs.** The existing compare/summarize essays are the weakest artifacts in the product — they are unverifiable by construction. Convert them to computed results with LLM assistance at the edges (E10 is the template).
- **Don't impose IRR universally.** For reflexive TA it is a category error; Braun & Clarke are explicit. Make it a per-tradition option (A14).
- **Don't market full automation.** Every study reviewed here — including the most favourable ones — concludes that LLMs should *augment, not replace*. Overclaiming is the fastest way to lose the academic audience the rest of this roadmap is built to win.

---

# Part 9 — Sources

**Methodology and coding traditions**
- Saldaña, J. *The Coding Manual for Qualitative Researchers* (4th ed.) — [publisher](https://www.amazon.com/Coding-Manual-Qualitative-Researchers/dp/1529731747), [review](https://nsuworks.nova.edu/tqr/vol14/iss4/14/)
- Braun & Clarke reflexive thematic analysis — [worked example (Springer)](https://link.springer.com/article/10.1007/s11135-021-01182-y), [overview](https://delvetool.com/blog/reflexive-thematic-analysis)
- Hsieh & Shannon (2005), *Three Approaches to Qualitative Content Analysis* — [Sage](https://journals.sagepub.com/doi/10.1177/1049732305276687), [PubMed](https://pubmed.ncbi.nlm.nih.gov/16204405/)
- Gale et al. (2013), framework method — [PDF](https://pure-oai.bham.ac.uk/ws/files/16708327/Gale_Using_framework_method_BMC_Medical_Research_Methodology_2013.pdf), [summary](https://www.abdn.ac.uk/media/site/education/documents/Framework_analysis_according_to_Gale_et_al_Access.pdf)
- MacQueen et al. (1998), *Codebook Development for Team-Based Qualitative Analysis* — [PDF](https://qualquant.org/wp-content/uploads/text/MacQueen%20et%20al%201998.pdf), [Sage](https://journals.sagepub.com/doi/10.1177/1525822X980100020301)

**Rigor**
- Lincoln & Guba trustworthiness — [Walden summary PDF](https://studyhall.waldenu.edu/dpsy2017/wp-content/uploads/sites/5/2017/04/Trustworthiness.pdf), [Nowell et al., *Thematic Analysis: Striving to Meet the Trustworthiness Criteria*](https://journals.sagepub.com/doi/pdf/10.1177/1609406917733847), [Stahl & King (ERIC)](https://files.eric.ed.gov/fulltext/EJ1320570.pdf)
- O'Connor & Joffe (2020), *Intercoder Reliability in Qualitative Research: Debates and Practical Guidelines* — [Sage](https://journals.sagepub.com/doi/10.1177/1609406919899220)
- [Inter-rater reliability in qualitative coding: considerations for its use (QualPage)](https://qualpage.com/2023/08/31/inter-rater-reliability-in-qualitative-coding-considerations-for-its-use/), [ATLAS.ti on why Cohen's kappa is a poor choice](https://atlasti.com/research-hub/measuring-inter-coder-agreement-why-cohen-s-kappa-is-not-a-good-choice), [Krippendorff's alpha methodological notes](https://www.k-alpha.org/methodological-notes)
- Hennink et al. (2017), *Code Saturation Versus Meaning Saturation* — [Sage](https://journals.sagepub.com/doi/10.1177/1049732316665344); [Saturation: conceptualization and operationalization (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC5993836/); [Sample size for saturation: debates and strategies](https://www.sciencedirect.com/science/article/pii/S2949916X24001245)

**Transparency and reporting**
- Jones, K. M. L. (2025), *Generative AI in Qualitative Research and Related Transparency Problems: A Novel Heuristic for Disclosing Uses of AI* (**TROUT-AI**) — [Sage](https://journals.sagepub.com/doi/10.1177/16094069251404329), [full text PDF](https://scholarworks.indianapolis.iu.edu/server/api/core/bitstreams/0cc4b756-133c-41a1-983b-274710449cfe/content)
- [SRQR and COREQ Reporting Guidelines for Qualitative Studies (JAMA Surgery)](https://jamanetwork.com/journals/jamasurgery/fullarticle/2778475); [SRQR vs COREQ vs ENTREQ guide](https://editverse.com/srqr-coreq-or-entreq-a-guide-to-qualitative-research-reporting-standards/)
- AI disclosure policy: [Defining the Boundaries of AI Use in Scientific Writing (JKMS)](https://jkms.org/DOIx.php?id=10.3346%2Fjkms.2025.40.e187); [When and how to disclose AI use — AMEE Guide 192](https://www.tandfonline.com/doi/full/10.1080/0142159X.2025.2607513); [When should disclosure be mandatory, optional, or unnecessary?](https://www.tandfonline.com/doi/full/10.1080/08989621.2025.2481949); [Journal AI policies (Scholastica)](https://blog.scholasticahq.com/post/journal-ai-policies/)
- Annotation for Transparent Inquiry — [NSF PAR](https://par.nsf.gov/biblio/10140037-annotation-transparent-inquiry-transparent-data-analysis-qualitative-research), [ATI in QCA (Cambridge)](https://www.cambridge.org/core/journals/ps-political-science-and-politics/article/abs/how-annotation-for-transparent-inquiry-can-enhance-research-transparency-in-qualitative-comparative-analysis/7F01EC75BCF5BAA4E1A3F3EF6446E1C0); [Transparency in Qualitative Research (Moravcsik)](https://www.princeton.edu/~amoravcs/library/TransparencyinQualitativeResearch.pdf)
- [Qualitative Data Repository](https://qdr.syr.edu/about); [Harvard Library guide to qualitative repositories](https://guides.library.harvard.edu/qualitative/repository)
- REFI-QDA — [standard home](https://www.qdasoftware.org/), [project page](https://www.qdasoftware.org/project), [spec PDF v1.5](https://openqda.github.io/refi-tools/docs/standard/REFI-QDA-1-5.pdf), [MAXQDA import/export](https://www.maxqda.com/help/report-and-export/export-and-import-refi-qda-projects), [ATLAS.ti QDPX](https://doc.atlasti.com/ManualWin.v22/Export/ExportQDPXUniversalDataExchange.html), [Quirkos overview](https://www.quirkos.com/learn-qualitative/refi-qda-exchange-atlasti-nvivo-maxqda.html)

**Ethics of social-media / Reddit research**
- Gliniecka, M. (2023), *The Ethics of Publicly Available Data Research: A Situated Ethics Framework for Reddit* — [Sage](https://journals.sagepub.com/doi/10.1177/20563051231192021)
- Reagle, J., *Disguising Reddit sources and the efficacy of ethical research* — [author copy](https://reagle.org/joseph/2020/mask/disguise.html), [ACM/Springer](https://dl.acm.org/doi/10.1007/s10676-022-09663-w)
- [A Systematic Review of Ethical Considerations in Reddit Research (ACM)](https://dl.acm.org/doi/pdf/10.1145/3633070)

**LLMs in qualitative analysis**
- [Large language models for thematic analysis in healthcare research: a blinded mixed-methods comparison with human analysts (PLOS Digital Health)](https://journals.plos.org/digitalhealth/article?id=10.1371%2Fjournal.pdig.0001189)
- [Assessing the Reliability of Large Language Models for Deductive Qualitative Coding (arXiv 2507.14384)](https://arxiv.org/pdf/2507.14384)
- [Large Language Models in Thematic Analysis: Prompt Engineering, Evaluation, and Guidelines (arXiv 2510.18456)](https://arxiv.org/pdf/2510.18456)
- [From Assistance to Autonomy — A Researcher Study on the Potential of AI Support for QDA (arXiv 2501.19275)](https://arxiv.org/pdf/2501.19275)
- [LOGOS: LLM-driven End-to-End Grounded Theory Development and Schema Induction (arXiv 2509.24294)](https://arxiv.org/pdf/2509.24294)
- [QualiGPT (arXiv 2407.14925)](https://arxiv.org/pdf/2407.14925); [CoAIcoder (ACM TOCHI)](https://dl.acm.org/doi/abs/10.1145/3617362); [Putting Tools in Their Place (PACM HCI)](https://dl.acm.org/doi/10.1145/3479856); [Making Human-AI Contributions Transparent in Qualitative Coding (CSCL 2024)](https://repository.isls.org/bitstream/1/10537/1/CSCL2024_3-10.pdf)
- [Leveraging AI to Enhance Qualitative Research: case studies across the EU (IJQM)](https://journals.sagepub.com/doi/full/10.1177/16094069251365766)

**Statistical validity of LLM annotations**
- [LLM Hacking: Quantifying the Hidden Risks of Using LLMs for Text Annotation (arXiv 2509.08825)](https://arxiv.org/pdf/2509.08825)
- Egami et al., *Using Large Language Model Annotations for Valid Downstream Statistical Inference: Design-Based Semi-Supervised Learning* — [arXiv 2306.04746](https://arxiv.org/html/2306.04746v1), [slides](https://naokiegami.com/paper/dsl_slide.pdf)
- [What Is Actually Being Annotated? Inter-Prompt Reliability as a Measurement Problem (arXiv 2604.16413)](https://arxiv.org/pdf/2604.16413)
- [Can Large Language Models Transform Computational Social Science? (arXiv 2305.03514)](https://arxiv.org/pdf/2305.03514)

**Tools and market**
- [AI Features in QDA Software 2026: NVivo, Delve, MAXQDA, ATLAS.ti, Dedoose, Quirkos & Taguette compared (Delve)](https://delvetool.com/blog/ai-features-in-qda-software)
- [Best qualitative data analysis software comparison (Lumivero)](https://lumivero.com/resources/blog/best-qualitative-data-analysis-software/); [MAXQDA vs ATLAS.ti 2026](https://skimle.com/blog/maxqda-vs-atlas-ti-qualitative-analysis-software-2026); [NVivo alternatives 2026](https://skimle.com/blog/nvivo-alternatives-2026-academic-researchers)
- Open source: [Taguette](https://www.taguette.org/), [University of Arizona open-source QDA guide](https://libguides.library.arizona.edu/qual-analysis/opensource), [NYU FLOSS QDA guide](https://guides.nyu.edu/QDA/FLOSSQDA)
- CAQDAS analysis features: [MAXQDA Code Relations Browser](https://www.maxqda.com/help/visual-tools/code-relations-browser-visualizing-overlapping-codes), [NVivo 15 distinguishing features (Surrey CAQDAS Networking Project)](https://www.surrey.ac.uk/sites/default/files/2026-01/nvivo-15-distinguishing-features.pdf)
- UX-research segment: [Best UX research repository tools 2026](https://www.koji.so/blog/best-ux-research-repository-tools-2026), [Dovetail AI review (Looppanel)](https://www.looppanel.com/blog/dovetail-ai)
- Computational social science: [The 4CAT Capture and Analysis Toolkit](https://journal.computationalcommunication.org/article/view/4752), [Communalytic](https://communalytic.org/), [The Pushshift Reddit Dataset (ICWSM)](https://ojs.aaai.org/index.php/ICWSM/article/view/7347)
- Local models / privacy: [Keeping private patient data off the cloud: comparison of local LLMs (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S3050577125000180), [Running LLMs locally with Ollama](https://www.freecodecamp.org/news/protect-sensitive-data-with-local-llms/)
