# Qualitative Coding in the Social Sciences — Methods, Rigor, Transparency, Competitors, and Expansion Avenues

**Prepared:** 2026-08-23 · **Revised:** 2026-08-28, 2026-09-07, 2026-09-12
**Subject:** Research briefing for the Qualitative Coding Tool (this repository)
**Purpose:** Establish what qualitative coding actually requires as a *method*, what standards of rigor and transparency the field enforces, what comparable tools already do, and — the main deliverable — an enumerated set of concrete avenues for expanding this application.

**What changed in the 2026-09-12 status revision.** The completed campaign added deterministic analysis-ready exports and a project bundle, corpus coverage, stronger job accounting and terminal-state behavior, and a revised comparison architecture. Deterministic codebook comparison now belongs beside coding comparison in version history. LLM-powered codebook and coding comparisons are restored as stored, viewable cross-artifact analyses and are included in project export. This status is owner-declared while the implementation session completes; this documentation update does not independently re-audit its code.

**What changed in the 2026-09-07 revision.** Sections §5.4, Part 6, and Parts 7–8 were re-audited against the then-current codebase: implemented avenues removed, partially-implemented ones re-rated (S/M/L and ★) with an explanation of what remained, and Part 8's top-ten and roadmap re-ranked. Parts 1–5.3 (the literature review) and Part 9 (sources) were unchanged — they are not claims about this codebase.

The headline change since the earlier revisions is the **human-in-the-loop editor rewrite**: filtering, codebook generation, and coding each have a single entry point where the researcher works by hand and the AI proposes into a review tray. Row memos, retrieval filters, coder attribution, and per-version AI-assist provenance reinforce that design. The numbered avenues now remain in place as stable historical identifiers; shipped and superseded entries are marked rather than removed, so the document is no longer presented as a live numerical backlog.

---

## 0. How to read this document

- **Parts 1–3** are the methodological background: the steps of qualitative coding, the rigor expected, the transparency required. These are the *requirements* the tool is implicitly being judged against.
- **Part 4** covers the empirical evidence on LLM-assisted coding — what actually works, and what the failure modes are.
- **Part 5** is the competitive landscape.
- **Part 6** is an honest, code-grounded gap analysis of the app as it stands today.
- **Part 7** is the payload: **83 historical expansion avenues**, grouped into nine themes. Completed and superseded entries remain for traceability; use the roadmap audit rather than the raw count as the dispatch backlog.
- **Part 8** sequences them into a roadmap and names the ten highest-leverage bets.
- **Part 9** lists sources.

For campaign execution, use `qualitative-coding-ticket-status.md` for current ticket state, `qualitative-coding-implementation-tickets.md` for the durable contracts, and `agent-worktree-orchestration-process.md` for the operating procedure. This research file never authorizes a worker assignment by itself.

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

*Updated 2026-09-07 — see the note at the top of Part 6 for what shipped since the previous revision.*

| Axis | This app | Best in class |
|---|---|---|
| **Human-in-the-loop discipline** | **Strong — best in class** | *Nobody else enforces this.* The one-shot AI routes were **deleted**: filtering, codebook generation and coding each have exactly one entry point, a workspace where the researcher works by hand and the AI can only *propose*. Proposals land in a review tray and create nothing until an explicit human submit; a row coded by hand is never overwritten by an AI recode |
| AI-native pipeline | **Strong** — background jobs, model choice, map-reduce over context limits, structured JSON I/O with a strict-decoding tier — now wired as an in-editor assistant rather than a batch generator | ATLAS.ti, LOGOS |
| Cost model | **Strong** — BYO OpenRouter key, free models selectable; recode is scoped to a chosen subset so cost tracks what the researcher actually wants re-examined | NVivo/MAXQDA charge $250+/yr |
| Lineage/provenance foundation | **Strong** — a git-like version spine (`artifact_versions`/`artifact_edges`/`codebook_codes`), sealed commits carrying model/job/prompt provenance, a one-hop lineage graph, a structural version diff, and SCD-2 row history | 4CAT |
| Evidence integrity | **Strong** — every AI-coded quote resolves to exact character offsets against the source or is rejected before storage; codes and item ids validated the same way | Nobody in the market does this |
| Analytic annotation | **Good** — free-text row memos on raw/filtered/coding artifacts, carried forward into every derived artifact, plus per-quote notes | MAXQDA, NVivo |
| Retrieval | **Fair** — rows filterable by code, by coded/uncoded, and by substring search, readable as of any historical version | MAXQDA, NVivo (boolean/proximity queries) |
| Manual coding UX | **Good** — 3-pane reader, select-text-to-tag, `1`–`9` code shortcuts, `j`/`k` navigation, session-batched saves | Taguette, MAXQDA |
| Data ingest breadth | **Weak** — Reddit `.zst` only | NVivo, 4CAT |
| **AI-assist disclosure** | **Good — resolved** | `coding_entries.coder`/`coder_model` (per-quote) and `artifact_assists` (per-version: model, prompts, accepted/dismissed counts, read from the job itself) now record exactly what the AI contributed, without touching `origin`/`model` on the version. Closes what was GAP-4 |
| Rigor apparatus (IRR, saturation) | **Absent** | Nobody does this well — *open territory* |
| Transparency/reporting output | **Fair** — deterministic CSV/JSON, long/wide coding exports, code summaries, and a project bundle now exist; a methods section and AI-disclosure report do not | Nobody does disclosure reporting well — *open territory* |
| Interoperability | **Partial** — the deterministic project bundle makes the app's own artifacts portable, including stored comparisons, but REFI-QDA `.qdc`/`.qdpx` remains absent | REFI-QDA members |
| Collaboration | **Absent** — single-owner | Dedoose, Delve, Taguette |
| Analysis/visualization | **Fair** — code frequency and corpus coverage are shown; deterministic codebook/coding history comparison and stored LLM cross-artifact comparison cover different analytic questions; no co-occurrence or crosstabs | MAXQDA, NVivo |

---

# Part 6 — Gap analysis of the application as it stands

**What shipped since the previous revision.** The pipeline was rebuilt around **human-in-the-loop editors**, and this is the most methodologically consequential change the codebase has made. The one-shot AI endpoints (`/api/filter-data/`, `/api/generate-codebook/`, `/api/apply-codebook/`) were **retired outright**; filtering, codebook generation and coding now each have a single entry point — a 3-pane workspace where the researcher works by hand with the data in view and the AI runs as an assistant that only *proposes*. Concretely: the **filter editor** proposes rows from the undecided pool only and can be re-run without re-litigating decided rows; the **codebook editor** sends the current draft with every run so repeated passes propose only what's missing, routes every proposal to a **review tray** showing all of its fields (definition, inclusion, exclusion, keywords, example) for individual accept/dismiss, and remembers dismissals; the **coding editor** creates the artifact *uncoded*, supports select-text-to-tag with `1`–`9` code shortcuts and `j`/`k` navigation, offers `Select all`/`Uncoded (N)` subset selection, stages AI recode output as reviewable proposals, and guarantees that **a row coded by hand is never overwritten by a recode**. Alongside this: **row memos** landed (`RowMemo`, `memo_repo`/`memo_service`/`memo_routes`, `MemoEditor.jsx`) — free-text analytic notes on any row of a raw/filtered/coding artifact, carried forward automatically into every derived artifact — and the rows API gained **retrieval filters** (`only=coded|uncoded`, `code=`, `q=` substring search, `version_no=` historical reads).

This is a direct, architectural implementation of the literature's central finding (§4.2): AI should *assist*, not *automate*, and researchers insisted on retaining autonomy over interpretive decisions. No competing tool enforces this at the level of "the one-shot path does not exist." **It also introduced one new gap, since closed** — see GAP-4 — because making the human the author of every artifact had the side effect of erasing the AI's contribution from the record entirely; B1/C2 (per-quote coder attribution, per-version assist provenance) have since restored it through a channel separate from `origin`/`model`.

The subsequent campaign closed two other major product gaps. Analysis-ready CSV/JSON exports and a deterministic project bundle let coded work leave the application. Comparison is now deliberately split by epistemic role: deterministic codebook and coding comparison explain changes between versions of one artifact, while restored LLM-powered codebook and coding comparison interprets separate artifacts. LLM comparison results are stored as viewable files and travel with project export rather than masquerading as computed agreement statistics.

Gap IDs are renumbered to reflect only what remains; the mapping to previous IDs is kept in parentheses for traceability.

| # | Observation | Where | Why it matters methodologically |
|---|---|---|---|
| GAP-1 *(was 1, softened)* | **No sampling strategy beyond `ORDER BY RANDOM()`.** Purposive selection is now *possible by hand* — the editors let a researcher read and hand-pick rows, and `POST /api/coding/manual` accepts explicit row ids — but there is still no *supported, recorded* strategy (stratified, maximum-variation, extreme-case), and `sample_percentage` still draws at random. | `raw_data_repo.py::sample_submissions`/`sample_comments`; `coding/manual` | Hand-picking is a real purposive workflow, so this is no longer a hard block — but a strategy the tool can *name and record* is what TROUT-AI T7 asks for, and hand-picking doesn't scale past a few hundred rows. |
| **GAP-2 *(RESOLVED)*** | **Native export was absent.** **Fixed:** deterministic CSV/JSON exports now cover codebooks, codings, memos, summaries, analysis-ready long/wide layouts, and a project bundle. Stored comparison artifacts are included in project export. | export routes/services and project-bundle export | Closed for native formats. REFI-QDA and publication-ready reporting remain separate interoperability/reporting work. |
| GAP-3 *(was 3)* | **Single-owner data model.** `File`/`Project` still carry only `user_id`; no sharing, roles, or teams. | `database.py` | Qualitative coding is overwhelmingly team-based. Blocks peer debriefing and any real double-coding/IRR workflow by construction. Now the *primary* structural blocker, since the single-researcher rigor stack is largely built. |
| **GAP-4 *(RESOLVED)*** | **AI assistance leaves no durable trace.** An artifact assembled with heavy AI help used to be stored identically to a hand-built one. **Fixed**: `coding_entries.coder`/`coder_model` (B1) record who produced each coded quote and with what model; `artifact_assists` (C2) records, per version, every assistant run that contributed — model, prompts, proposed/accepted/dismissed counts — sourced from the referenced `jobs` row rather than trusted from the client. `origin`/`model` on `ArtifactVersion` are untouched, exactly as this row originally recommended. | `backend/app/core/coder_rollup.py`, `backend/app/services/assist_service.py`, `storage_models.py::CodingEntry`, `versioning_models.py::ArtifactAssist` | Closed. TROUT-AI **T14**/**T15** are now satisfiable — see avenue C2 (shipped) and, downstream, C3/C4. |
| **GAP-5 *(RESOLVED, SCOPE CORRECTED)*** | **Comparison previously conflated structural history with cross-artifact interpretation.** **Fixed:** deterministic codebook comparison now lives in version history with the coding history comparison and matching UI; LLM-powered codebook and coding comparison is restored for separate artifacts, with results stored and viewable as files. | version-history comparison, LLM comparison jobs/views, comparison-file storage, project export | Closed as a product-architecture gap. LLM output remains interpretive and must not be presented as κ/α/AC1 or other computed reliability evidence. |
| GAP-6 *(was 6)* | **Second-cycle coding is absent.** The pipeline still ends at codes → prose summary. | whole pipeline | Codes are not themes. Under Braun & Clarke the tool now supports Phases 1–2 *well* (the editors add real familiarization, which it previously lacked) but still skips Phases 3–5 entirely. |
| GAP-7 *(was 7)* | **Reddit-only ingest** (`.zst` → `submissions`/`comments`). | `storage_models.py` | Excludes interviews, focus groups, open-ended survey items, documents — most of the qualitative research market. The editors make this gap *more* costly: a genuinely good hand-coding workspace is wasted on a corpus type most qualitative researchers don't have. |
| GAP-8 *(was 8)* | **In-flight jobs are still lost on restart** (API key held only in the runner's closure). | `jobs/service.py` (documented trade-off) | Less severe than before — the editors persist working state to `localStorage`, so a lost preview job no longer loses the researcher's decisions, only the run. |
| GAP-9 *(was 9)* | **Module-level model constants are still not rebound by the daily catalog refresh.** Reduced severity: every generated version records the model it actually used. | `ai_models.py` / `codebook_generator.py` | Reproducibility of a *specific* generated artifact is fine; "what will the default do tomorrow" is not. |
| GAP-10 *(was 10)* | **No PII handling or quote-traceability protection**, on a corpus of Reddit posts including sensitive communities (the repo's own sample is `bullying submissions.zst`). | ingest path | The ethics literature's central concern, unmitigated. Unchanged. |

**Fair summary, updated.** The original finding — "the engineering is well ahead of the methodology" — no longer holds on the *process* axis. The editors implement, architecturally, what the literature asks for: familiarization before coding, the analyst as author, AI as a proposer whose every suggestion is individually accepted or dismissed, memos written while reading, and iteration that doesn't re-litigate settled decisions. That is a genuinely strong methodological position, and it is the app's clearest differentiator.

What remains open is now more specific: **(1) methodological measurement** — no IRR, saturation, or calibrated agreement statistics; **(2) publication reporting and standard interoperability** — no methods/disclosure generator or REFI-QDA exchange; and **(3) collaboration** — no teams. Native export, AI-assist provenance, coverage, and the comparison split are now present. The next credibility gains come from explaining and validating results, not from adding another generic comparison mode.

---

# Part 7 — Expansion avenues

**83 historical avenues, in nine themes.** Each records what it is, why the literature demands it, where it lands in this codebase, and its original effort/impact. Completed and superseded entries remain in place for traceability and are not work requests.

## Theme A — Methodological depth: become a real QDA tool, not a coding script

> **Resolved since the last revision:** *analytic memos* (`RowMemo` + `memo_routes`/`memo_service`/`memo_repo` + `MemoEditor.jsx` — free-text notes on any row, carried forward into every derived artifact, with a `✎` marker in row lists; the model's own docstring cites GAP-4 of the previous revision). **Resolved earlier:** directed/deductive mode, codebook versioning with structural diffs, MacQueen-complete code structure, conversation-aware coding. Five of the original fifteen avenues in this theme are done.

**A1. Second-cycle coding as a first-class artifact.** ★★★★★ · **L**
Add a `theme` artifact type: codes → categories → themes, with each theme carrying constituent codes, a definition, boundary conditions, and exemplar quotes. This is Braun & Clarke Phases 3–5 and Saldaña's Second Cycle. **Now the largest single methodological gap**, because the editors closed the Phase 1–2 gap so thoroughly: the app supports familiarization and coding properly and then stops dead before theme development. *Where:* new `file_type`, new service; `ArtifactEdge` already models typed, version-pinned parent links, and the codebook editor's proposal-tray pattern is the obvious UI template for proposing themes over existing codes.

**A2. Framework matrix view (cases × themes).** ★★★★ · **M**
The Gale et al. charting step. Rows = cases (post, author, subreddit, or an imported participant id), columns = codes/themes, cells = the coded excerpts, with drill-down. *Where:* pure read-model over `coding_entries` joined to `submissions`; the rows endpoint's existing `code=`/`only=` filters are most of the query layer already.

**A3. Extending the sample into an existing artifact.** ★★★★ · **S** *(substantially narrowed — was "iterative/theoretical sampling loop," ★★★★ · M)*
**The iteration loop itself shipped** across all three editors: the filter assistant proposes only from the undecided pool, the codebook assistant is sent the current draft so repeated runs propose only what's missing (and remembers dismissals), and the coding editor recodes arbitrary subsets with `Uncoded (N)` as a one-click selector. That is constant comparison in practice. What remains is narrow but real: a coding artifact's row set is fixed at creation (`POST /api/coding/manual` samples or takes explicit ids, once), so a researcher cannot *pull more data in* as the analysis develops — which is precisely what theoretical sampling requires. *Where:* an "add rows" path reusing `raw_data_repo.copy_rows_by_id` + `memo_repo.copy_memos_by_id`, committed as an ordinary new version.

**A4. Reflexivity / positionality statement per project.** ★★★ · **S**
A structured field on `Project`, prompted at creation, that flows into the generated methods appendix (Theme C). Under TROUT-AI, reflexivity now explicitly extends to *the technological* dimension — which tools, which models, what the team understands about their limits. Complements the row memos that already ship: memos capture what you noticed, this captures who was noticing.

**A5. Disconfirming-evidence search.** ★★★ · **S** *(narrowed — was "negative case analysis")*
The "surface what's uncoded" half **shipped**: `only=uncoded` on the rows endpoint, an `Uncoded (N)` selector in the coding editor, and status filters in the filter editor. What remains is the analytic half — an explicit pass that asks, for a named code or theme, "find data in this corpus that contradicts it," presented for review in the same proposal tray the codebook editor already uses. Cheap, and one of the named credibility techniques in §2.2 that nothing in the market implements.

**A6. Saturation tracking and reporting.** ★★★★★ · **M**
The app can record **new codes per assistant run** essentially for free — and the codebook editor's design makes this *easier than it was*, because it already sends the current draft with every run and knows exactly which proposals were novel versus already-covered (`_code_dedupe_key`). Plot the accumulation curve, distinguish **code saturation** ("no new codes") from **meaning saturation** ("no new dimensions of existing codes"), and emit a chart plus a sentence for the methods section. Nobody in the market does this; it converts an arbitrary stopping point into a defensible one. **Still fully open, still one of the highest-value items in the document, and now cheaper to build than when it was first proposed.**

**A7. Purposive, stratified, and maximum-variation sampling.** ★★★ · **M** *(downgraded — was ★★★★)*
Stratify by subreddit, time window, score, word count, thread depth, or author; maximum-variation sampling via embedding diversity; extreme/deviant case sampling; record the strategy on the artifact for TROUT-AI T7. Downgraded because the editors made hand-picking a real workflow (see GAP-1) — this is now about *scale and recordability* rather than about making purposive selection possible at all.

**A8. In-vivo coding mode.** ★★ · **S**
A first-cycle method where codes are participants' own words verbatim. Trivial as a variant of the now-structured generator prompt, and it fits the proposal-tray flow unchanged.

**A9. Method-guided workflows.** ★★★★ · **M**
A project-creation step: "Which tradition? Reflexive TA / grounded theory / content analysis / framework method." The choice configures the pipeline — which prompts, whether IRR is offered (it should be suppressed for reflexive TA), which stages appear, which reporting template is generated. The editors give this something concrete to configure now, rather than being an abstraction over a one-shot pipeline.

**A10. Code hierarchy / code tree.** ★★ · **S**
The identity groundwork is done (`code_uid`/`family_uid` are stable and rename-proof). What remains is small: the model is still a flat two-level family → code structure with no arbitrary-depth nesting. Needed for full `.qdc` fidelity (D1).

## Theme B — Rigor and validation: the biggest open territory

> **Resolved since this revision:** *B1, coder identity on every coded segment* — see below. **Resolved since the last revision:** *the human adjudication queue* — the interaction this theme's original B5 called for is now the app's primary UI, not a missing feature. The codebook editor routes every AI proposal to a review tray showing all of its fields for individual accept/dismiss (with dismissals remembered across runs); the coding editor stages recode output as reviewable proposals in the same session as manual tags, commits only on an explicit Save, and never lets an AI recode overwrite a hand-coded row; tagging is keyboard-driven (`1`–`9`, `j`/`k`). **Resolved earlier:** evidence-span verification, code-name validation, post-ID validation, version-level provenance, uncoded-residue visibility. Seven of the original eighteen avenues in this theme are done.

**B1. Coder identity on every coded segment. — RESOLVED** ★★★★★ · **S**
Shipped: `coding_entries.coder` (`"human"`/`"ai"`) and `coder_model`. Offsets, stable `code_uid`s, and multiple quotes per (item, code) had already shipped, so this really was just the identity column. **Its value went up with the editors**: the app genuinely mixes hand-coded and AI-proposed entries in one artifact — and already distinguished them *behaviourally* (a hand-coded row is protected from recode) — and now records which is which too, rolled up per row (`core/coder_rollup.py`) rather than stored redundantly. Prerequisite for double-coding, IRR, and half of C2 (also shipped) — B2/B3 below are now genuinely unblocked, not just theoretically so.

**B2. Blind double-coding workflow.** ★★★★ · **M**
Assign a random 10–25% subset to a second coder (human or a different model) with the first coder's decisions hidden, then reconcile. Implements O'Connor & Joffe's concrete guidance (§2.3). The reconciliation UI is largely a variant of the review tray that already exists. Needs B1 and, for human-human, F1.

**B3. Inter-coder reliability metrics.** ★★★★★ · **M**
Percent agreement, Cohen's **κ**, Krippendorff's **α**, Fleiss' κ, and **Gwet's AC1** — over human–human, human–AI, and AI–AI pairs. Report all of them with an explanation of the kappa paradox (κ = 0.34 alongside AC1 = 0.93 on the same data is the canonical illustration), plus a per-code agreement table showing *which* codes are unreliable. *Where:* pure computation over `coding_entries` once B1 lands; a new `services/reliability_service.py`. **Still the single highest-value unbuilt item in Theme B**, and the app is now unusually well-positioned for it: it has verified spans, stable code identity, and a mixed human/AI coding record — everything except the labels saying who did what.

**B4. Multi-model ensemble coding.** ★★★★ · **S**
Run the same codebook through 2–3 models, keep unanimous codes, route disagreements to review. The building blocks are all present — recode already accepts a caller-chosen model over a chosen subset, and the proposal tray is already the disagreement-review surface. What's missing is the fan-out-and-diff orchestration. Triangulation by analyst, mechanized; the single-vendor incumbents cannot easily match it.

**B5. Prompt-sensitivity / robustness analysis.** ★★★★ · **M**
Run the same coding task under N paraphrased prompts and report label stability — *inter-prompt reliability*, the direct defence against LLM hacking, where "paraphrasing prompts can make nearly any conclusion appear significant" (§4.3). Treat prompts as versioned measurement instruments; the `prompts` table exists for storage but is still unversioned (C9).

**B6. Test–retest stability.** ★★★ · **S**
Re-run the identical prompt/model/data and report the proportion of identical decisions. Cheap, and it gives users a number for non-determinism.

**B7. Gold-standard validation sets.** ★★★★ · **M**
Let a user mark a hand-coded subset as gold, then score any AI run against it: accuracy, per-code precision/recall/F1, κ/α/AC1. **Materially easier now** — the coding editor produces genuine hand-coded rows as a matter of routine, and already tracks them well enough to protect them from recode, so the gold set is a labelling exercise over data the workflow generates naturally rather than a separate data-entry chore.

**B8. DSL / prediction-powered inference for downstream statistics.** ★★★★★ · **L** — *the most defensible differentiator available*
The Egami et al. workflow: LLM-code everything → randomly sample for expert annotation → doubly-robust estimation → report prevalence, subgroup differences and trends **with valid confidence intervals**. Converts "the model says 34% of posts express X" into "34% [95% CI 29–39%], corrected for classifier error against 200 human-verified cases." *Where:* builds on B7; the statistics are a contained numeric module. The editors supply the human-verified subsample this depends on as a natural by-product of use.

**B9. Per-decision confidence and abstention.** ★★★ · **M**
Ask the model for a confidence rating (or use logprobs where exposed), store it on the proposal, and **order the review tray by it** so the researcher's attention goes to the borderline cases first. The tray exists; it is currently unordered. This is now a small, high-return addition rather than a new subsystem.

**B10. Deterministic replay.** ★★★ · **S**
Half shipped (`ArtifactVersion.model`/`prompt_meta` on every generated commit). What remains: pin model **snapshot** ids rather than floating aliases, and record temperature/seed/sampling parameters (GAP-9). Backward provenance is honest today; forward reproducibility is not.

**B11. Built-in evaluation harness.** ★★★ · **M**
Fixture corpora with expert codings, run in CI, tracking agreement over time so prompt changes are evaluated rather than vibed. `tests/backend/` already mirrors the package structure, and the editors' pure state modules (`filterEditorState.js`, `codebookEditorState.js`) are already unit-tested — the precedent is set.

**B12. Bias and coverage checks.** ★★★ · **M**
Report whether coding density varies systematically by post length, score, subreddit, or time — a proxy for under-coding some voices. LLM annotation error is well documented to be **non-random**, which is exactly why DSL exists.

## Theme C — Transparency and reporting: turn compliance into a feature

> **Resolved since this revision:** *C2, AI-assist provenance channel* — see below. **Resolved earlier:** full run provenance on every artifact, and the interactive lineage/provenance graph.

**C1. Automatic audit trail.** ★★★★ · **S**
Substantially shipped via the version spine: every save is a sealed `ArtifactVersion` with `origin`, `author_user_id`, `sealed_at`, and either a system-generated `message` or full model/prompt provenance. What remains is a **project-level rollup view** reading across every artifact's version history as one narrative timeline. With row memos and `artifact_assists` (C2) now landed, that timeline has genuine analytic content to show, not just mechanical events.

**C2. Record AI-assist contribution as its own provenance channel. — RESOLVED** ★★★★★ · **S**
Closed GAP-4. Shipped as `artifact_assists` (`versioning_models.py`): one row per assistant run, persisting what it contributed and what the human did with it — which job (`filter_preview`/`codebook_preview`/`recode_items`), how many proposals, how many accepted versus dismissed, and which refs. `origin`/`model`/`system_prompt` on `ArtifactVersion` were left untouched, exactly as originally recommended — `assist_service.py` is the sibling channel instead, and it reads model/prompts from the referenced `jobs` row rather than trusting the client's claim. The frontend's own bookkeeping (`filterEditorState.js`'s `aiAdded`, `codebookEditorState.js`'s `aiAccepted`/`dismissed`, `useViewCodingPage.js`'s recode staging), which used to be thrown away at submit, now reduces into the `assist_runs` payload. **TROUT-AI T14 and T15** are now satisfiable — C3 and C4 below are unblocked, not just theoretically so.

**C3. One-click methods appendix.** ★★★★★ · **M**
Generate a draft Methods section: data source and date range, sampling/selection strategy and n, model + version, verbatim system and user prompts, codebook version history, IRR statistics (B3), saturation curve (A6), evidence-verification rates (computable today from `evidence_match`'s reject counts), and human-versus-AI contribution rates (C2). Populate a **COREQ (32-item)** or **SRQR (21-item)** checklist with what the tool knows and mark the rest for the user. Substantially a rendering task over data the app already holds.

**C4. TROUT-AI disclosure generator.** ★★★★★ · **M**
Walk the 20 questions across the 5 themes, pre-answering what the system knows (T1 roles, T7 selection logic, T9 storage, T12 saturation, T14 AI's coding role, T15 the prompt log) and prompting the researcher for the rest (T2 AI literacy, T8 IRB discussion). Output a submission-ready disclosure block. **No competing tool does this**, and the app's answer to T14 is now genuinely distinctive — "the AI proposed, a human accepted each item individually, and here are the counts" is a stronger disclosure than any competitor can truthfully make. C2 (now shipped) is what makes this truthful; remaining work here is purely the rendering layer.

**C5. AI disclosure statement for journals.** ★★★★ · **S**
A short COPE/ICMJE-compliant paragraph naming tool, model, version and tasks, correctly targeted at the **Methods** section (analysis/coding) rather than Acknowledgements (writing).

**C6. Reproducibility bundle export.** ★★★★ · **M** *(partially shipped)*
A deterministic native project bundle now exports project artifacts, analysis-ready data, and stored comparison files. What remains for a true reproducibility deposit is a documented manifest covering source hashes/acquisition recipes, complete prompt and model settings, the full audit trail, external schema guarantees, and validation for QDR/OSF/Zenodo deposit.

**C7. ATI-style annotated evidence export.** ★★★ · **S**
Claim → annotation → excerpt → source. This is now *exactly* the `code → quote → start_offset/end_offset → post_id` chain in `coding_entries`, and row memos supply the "analytic note" layer ATI also expects. Export as ATI-compatible annotations so reviewers can click a claim and land on the underlying data. Novel; nobody offers it.

**C8. Shareable read-only artifact links.** ★★★ · **M**
Peer debriefing and reviewer access without an account. Delve markets peer debriefing as a headline feature; this is the minimal version. Needs some notion of a scoped read token, since there is still no multi-user model (Theme F).

**C9. Prompt library with versioning.** ★★★ · **S**
The `prompts` table and `PromptManager.jsx` remain unversioned — extend to immutable versions, hashes, and "which artifacts used this prompt version." Required by TROUT-AI T15 and by B5. The gap is more conspicuous now that the assistant is invoked repeatedly within a single editing session rather than once per artifact.

**C10. Cost and token accounting. — RESOLVED** ★★★ · **S**
Jobs now record calls, duration, tokens, and cost when known, while preserving unknown values as unknown rather than inventing zeroes. Project-level reporting can build on the stored accounting without changing the job contract.

## Theme D — Interoperability and data ingest: stop being an island

**D1. REFI-QDA Codebook (`.qdc`) import/export.** ★★★★★ · **S**
Round-trip codebooks with NVivo, ATLAS.ti, MAXQDA, Quirkos, f4analyse. The data model is most of the way there: `CodebookCode` has stable, rename-proof identity, discrete definition/inclusion/exclusion/keywords/example fields, and explicit ordering — close to a direct field-for-field mapping onto `.qdc`'s XML. What remains is a serializer/deserializer. Depends on A10 only for deeply nested codebooks; a flat-family export needs nothing further. **Best single interoperability investment.**

**D2. REFI-QDA Project (`.qdpx`) export.** ★★★★ · **M**
Full project exchange — sources, codes, coded segments, memos, variables. **Both preconditions have now shipped**: character offsets (via the evidence-matching rewrite) and memos (via `RowMemo`), which `.qdpx` models as a first-class element. This is now a serialization job over data that exists in the right shape, sequenced after D1.

**D3. Plain tabular exports. — RESOLVED** ★★★★★ · **S**
Shipped deterministic CSV/JSON exports for codebooks, coded segments, memos, summaries, code frequencies, and analysis-ready long/wide layouts, plus a deterministic project bundle. Stored LLM comparison files are included in project export. XLSX remains unnecessary until a real consumer requires it.

**D4. Generic text ingest.** ★★★★★ · **L**
Interview transcripts, focus groups, open-ended survey responses, field notes, documents (PDF/DOCX/TXT), and generic CSV with a column mapper. **This is the biggest market-size lever in the document**, and the editors raise its value sharply: the app now has a hand-coding workspace good enough that interview researchers would plausibly want it, applied to the one data type they don't have. *Where:* a `documents`/`text_units` table alongside `submissions`/`comments`, generalizing the pipeline over a "unit of analysis" abstraction; `core/item_types.py`'s submission/comment split is a workable template for a third type.

**D5. Additional social platforms.** ★★★ · **L**
X/Bluesky/Mastodon/YouTube/Telegram — or, far cheaper, **import from 4CAT and Communalytic exports**. Let the CSS tools do acquisition; do coding.

**D6. Arctic Shift / modern Reddit acquisition.** ★★★ · **M**
Pushshift's public service is gone; Arctic Shift is the successor. In-app acquisition (subreddit, date range, query) beats "find a `.zst` somewhere," and lets the tool record acquisition parameters as provenance.

**D7. Audio/video with transcription.** ★★★ · **L**
Whisper-based transcription with timestamps, so codes anchor to time offsets. Quirkos sells exactly this at $12/month; the UX-research tools treat it as table stakes.

**D8. Multilingual coding.** ★★★ · **M**
Code in the source language, with optional translation whose provenance is recorded (MAXQDA advertises 11 languages). Important for non-Anglophone research.

**D9. Public API + Python client.** ★★★ · **M**
The backend is already a clean REST API. A documented API and a thin notebook client makes the tool scriptable for computational researchers — the population most likely to code 100k posts.

**D10. Import an existing hand-coded dataset.** ★★★★ · **S**
Upload a CSV of human codings to serve as the gold standard (B7) or as coder A in an IRR comparison. Instant credibility path for a sceptical researcher: "show me it agrees with what I already did."

## Theme E — Analysis and visualization: make the coded data answer questions

**E1. Code frequency and distribution dashboard. — RESOLVED** ★★★ · **S**
The corpus coverage dashboard presents coded/uncoded coverage, coverage percentage, code-family rollups, and code counts in the coding workspace. More advanced distribution analysis belongs in the later crosstab and reliability work rather than another coverage widget.

**E2. Code co-occurrence matrix and network.** ★★★★ · **M**
Which codes appear together on the same post/thread? MAXQDA's Code Relations Browser is the reference. A SQL self-join on `coding_entries`; with real offsets this also supports proximity- and overlap-based co-occurrence, not just same-item.

**E3. Crosstabs by attribute.** ★★★★ · **M**
Code × subreddit, code × time window, code × score bucket, code × author-type. The mixed-methods bridge, and exactly what `submissions`' columns are for. NVivo's crosstab/matrix query is the reference.

**E4. Temporal trend analysis.** ★★★ · **M**
`created_utc` is already stored. Code prevalence over time, with change-point detection. Reddit corpora are longitudinal by nature and this is currently thrown away.

**E5. Quantitizing with honest error bars.** ★★★★ · **M**
Summative content analysis (Hsieh & Shannon) done properly: counts and proportions, corrected via B8 rather than reported raw.

**E6. Quote bank / evidence explorer.** ★★★ · **S** *(narrowed — the retrieval layer shipped)*
Browsing by code and searching text now exist (`code=`, `q=`, `only=` on the rows endpoint), and `HighlightedContent.jsx` renders excerpts in context. What remains is the *write-up-facing* view: a quote-centric list rather than a row-centric one, with starring/shortlisting for the paper draft and one-click copy with attribution. Small, and it is the artifact researchers actually need at drafting time.

**E7. Boolean and proximity search.** ★★★ · **S** *(narrowed — substring search shipped)*
`q=` gives case-insensitive substring search over title/body today. What remains: Postgres full-text search with boolean/proximity operators, and extending search to *evidence text and memos*, not just row bodies. Basic CAQDAS retrieval.

**E8. Semantic search and embedding-based exploration.** ★★★ · **L**
Cluster the corpus, surface exemplars and outliers, let researchers read before coding. Less critical than it was — the editors' reader panes now provide real familiarization (Braun & Clarke Phase 1) that the app previously skipped entirely — but still the way to make familiarization *scale* past what a person can read.

**E9. Corpus code-density view. — RESOLVED THROUGH E1** ★★ · **S**
The coverage dashboard now exposes coded/uncoded balance and code-family density. A separate heatmap would duplicate that diagnostic unless a concrete spatial or temporal visualization requirement emerges.

**E10. Separate structural history comparison from interpretive cross-artifact comparison. — RESOLVED** ★★★★ · **S**
The initial proposal put deterministic comparison between arbitrary artifacts, but that overextended identity-based diffing into cases where string or stable-ID matches are usually uninformative. The implemented boundary is stronger: deterministic codebook comparison lives in version history and matches the existing coding version-history UI; LLM-powered codebook and coding comparison handles separate artifacts. LLM results are stored, viewable, and included in project export, while remaining explicitly interpretive rather than computed reliability evidence.

## Theme F — Collaboration: qualitative research is a team sport

No change — `File`/`Project` still carry only a single `user_id`. This theme is now **the most load-bearing unbuilt area in the document**: with the single-researcher workflow genuinely good, nearly everything left in Theme B (double-coding, human–human IRR, reconciliation) and C8 (peer debriefing) is blocked on the absence of a second user rather than on missing analytic machinery.

**F1. Teams and shared projects with roles.** ★★★★★ · **L**
Owner / analyst / reviewer / read-only. *Where:* the single-`user_id` ownership model in `database.py`; a `project_members` table plus authorization changes at `require_user_id` call sites.

**F2. Coding assignment and workload tracking.** ★★★ · **M**
Assign rows or subsets to coders, track progress, flag the double-coded subset. The coding editor's existing subset-selection UI is the natural surface for this.

**F3. Threaded discussion on codes and disagreements.** ★★★ · **M**
Where reconciliation actually happens. Preserve it — the disagreement record is itself audit-trail material. Row memos are the single-user precursor; this is the multi-user version.

**F4. Structured peer-debriefing mode.** ★★★ · **M**
An outsider gets read-only access plus a prompt list ("what would a sceptic say about this theme?"). Delve ships a version of this; it maps to a named credibility technique.

**F5. Coder training and calibration.** ★★★ · **M**
New coders code a calibration set, get scored against the gold standard, and see where they diverge — the "AI for onboarding new coders" use case researchers themselves nominated (arXiv 2501.19275). The keyboard-driven coding editor is a good training surface as-is.

**F6. Shared codebook library.** ★★★ · **M**
Publish and reuse validated codebooks across projects and users, with citation. Directed content analysis (shipped) needs a supply of codebooks; this creates one.

## Theme G — Ethics and compliance: the unclaimed high ground

No change — no PII handling, no local-model support, no retention policy anywhere in the codebase. Every avenue remains fully open.

**G1. PII detection and redaction at ingest.** ★★★★ · **M**
Usernames, real names, locations, handles, URLs, emails. Store the mapping separately so the analysis stays coherent while the working corpus is de-identified.

**G2. Quote traceability checker.** ★★★★★ · **M** — *novel; nobody offers it*
Before a quote goes into a paper, flag whether it is verbatim (and therefore search-engine locatable — the empirical finding is that **all** verbatim quotes and many reworded ones were found). Offer graduated protections: paraphrase, generalize, or synthesize a composite **vignette**, each labelled as such in the export. A different concern from `evidence_match.py`'s: that module checks a quote is *real*; this checks whether a real quote is *safe to publish*. The quote bank (E6) is its natural home.

**G3. Sensitive-community warnings.** ★★★ · **S**
Flag corpora from communities where the situated-ethics literature counsels extra care (mental health, self-harm, addiction, abuse, minors — the repo's own sample is `bullying submissions.zst`), and link the guidance.

**G4. IRB/ethics documentation helper.** ★★★ · **M**
Generate a data-handling description for an ethics application: what data, from where, where stored, which third parties see it (OpenRouter!), retention, de-identification. TROUT-AI T8/T9 make this a disclosure requirement, and most researchers do not realize their corpus is going to a third-party inference provider.

**G5. Local / self-hosted model support.** ★★★★★ · **L**
Ollama, vLLM, or any OpenAI-compatible endpoint, plus a configurable base URL. **A hard gate, not a nice-to-have:** many IRBs and most GDPR-governed institutions forbid sending participant data to a commercial API, and "data privacy" was the first concern researchers named. *Where:* `external/openrouter_client.py` still hardcodes `OPENROUTER_URL` as the single external-call seam — a contained change, and the architecture deserves credit for keeping that seam single through two rewrites.

**G6. Data retention, deletion, and encryption policy.** ★★★ · **M**
Per-project retention windows, hard delete, encryption at rest. TROUT-AI T9.

**G7. Consent and terms-of-use provenance.** ★★ · **S**
Record how the data was obtained, under what platform terms, and whether an ethics approval reference exists. Travels with the reproducibility bundle (C6).

**G8. Model/provider data-use transparency.** ★★★ · **S**
Show, per selected model, whether the provider trains on submitted data (OpenRouter exposes much of this). Free models are frequently the *least* privacy-preserving — and this app defaults to free models.

## Theme H — Positioning, market, and adjacent applications

The positioning claim is now materially stronger than in either previous revision. The app can say something no competitor can: **the one-shot "let the AI code it" path does not exist here — the AI can only propose, and a human accepted every item individually.** That is not marketing; it is enforced by the absence of the endpoints.

**H1. Target academic qualitative researchers explicitly.** ★★★★★ · **S**
The market gap is unambiguous: incumbents have rigor infrastructure but bolted-on AI at $250+/yr; UX-research tools have great AI but no methodological accountability. **Auditable, human-authored, statistically-honest AI-assisted coding** is unoccupied — and the editor architecture, evidence verification, and version provenance are now shippable proof points rather than aspirations. The remaining work to make the pitch complete is mostly Theme C (say what you did) and D3 (let it leave).

**H2. Teaching mode.** ★★★★ · **M**
Methods courses need exactly this: a scaffolded environment where students code by hand, compare against an instructor's gold standard, see their κ/α, and read the audit trail of their own decisions. **Now much closer to reality** — the keyboard-driven coding editor and the proposal-review discipline are, as-is, a good teaching artifact for what human-in-the-loop coding should look like. Institutional sales follow teaching adoption; NVivo's academic dominance was built this way.

**H3. Qualitative evidence synthesis / systematic review screening.** ★★★ · **L**
Title/abstract screening and thematic synthesis are structurally identical to filter → codebook → apply — and the filter editor's keep/skip-with-AI-suggestions loop is *precisely* the screening interaction, applied to the wrong data type. ENTREQ is the reporting standard. Large adjacent market; the main blocker is D4.

**H4. Policy consultation and open-response analysis.** ★★★★ · **M**
Government consultations, citizen assemblies, open-ended survey items — tens of thousands of free-text responses that must be coded *and* defended publicly. Arguably a better product-market fit than academia: same rigor demands, more budget, less tool lock-in. Depends on D4.

**H5. Content-moderation and trust-and-safety research.** ★★★ · **M**
Reddit-native ingest is an advantage here. Codebooks are policy taxonomies; IRR is already standard practice in that field.

**H6. Market/consumer research and support-ticket analysis.** ★★★ · **M**
The Dovetail segment. Lower rigor demands, higher willingness to pay, but crowded and well-funded — a secondary revenue line at most.

**H7. Institutional/campus deployment.** ★★★★ · **L**
Self-hosted (G5) + teams (F1) + SSO = a site licence. This is how CAQDAS is actually purchased — libraries and departments, not individuals.

**H8. Open-source the core, monetize hosting/institutional features.** ★★★ · **M**
Taguette, QualCoder and CATMA prove the demand for free and open QDA; none has credible AI. An open core with paid hosting, collaboration and compliance features is viable and credibility-generating.

**H9. Publish a validation study of the tool itself.** ★★★★★ · **M**
Run the pipeline against a published human-coded dataset and report agreement, hallucination rates and DSL-corrected estimates — the PLOS study's design. **Closer to feasible than ever**: the anti-hallucination pipeline already reports rejection counts, the editors produce genuine human codings to compare against, and the human/AI split is behaviourally tracked. Add B7 (gold sets) and B3 (agreement statistics) and the study is mostly a write-up. A citable validation paper is *the* adoption currency in academia.

**H10. Ship prompts as citable, versioned methods artifacts.** ★★★ · **S**
Publish the system prompts publicly with version numbers and a DOI so papers can cite "Codebook Generator prompt v2.1." Cheap, and it converts the model-drift gap (GAP-9) into a managed public contract.

## Theme I — Platform work that unblocks the rest

> **Resolved earlier:** structured outputs replacing the bespoke DSL parser (`CODING_JSON_SCHEMA`'s strict-decoding tier, with the regex path kept only as a fallback).

**I1. Durable job execution.** ★★★ · **M** *(downgraded — was ★★★★)*
An in-flight job still dies with the process because the API key lives only in the runner's closure. **Less severe now**: the editors persist working state to `localStorage` per source database, so a lost preview job costs the run but not the researcher's decisions — exactly the failure mode that used to be catastrophic. Still worth fixing for long recodes.

**I2. Resumable and idempotent batch coding.** ★★★ · **M**
Checkpoint per batch so a failure resumes rather than restarts. `ProgressTracker` already tracks batch progress — persist the completed batches too.

**I3. LLM response caching and deduplication.** ★★★★ · **M** *(upgraded — was ★★★)*
Cache on (model, prompt hash, params). **More valuable than before**: the editors invite repeated assistant runs over largely overlapping data within one session, so cache hit rates should be high and the cost saving direct. `prompt_meta` already hashes the rendered prompt.

**I4. Model pinning and catalog snapshots.** ★★★ · **S**
Bind model constants at call time, store the catalog snapshot per run, warn when a previously used model disappears (GAP-9). The artifact-level half shipped (`ArtifactVersion.model`); the forward-looking half remains.

**I5. Rate-limit and quota handling with clear user feedback.** ★★★ · **S** *(partially resolved)*
Partial, retryable-failure, failed, and cancelled jobs now have explicit terminal semantics, and salvaged output/accounting is preserved. Provider-specific quota messaging and resumable recovery remain part of I1/I2 rather than a new job state.

**I6. Batch-size and cost estimation before submitting. — RESOLVED THROUGH C10** ★★★ · **S**
The shared AI-assist flow now exposes estimated calls, duration, and cost where provider data permits, with unknown values represented honestly.

**I7. Streaming progress with partial results.** ★★★ · **M** *(upgraded — was ★★)*
Stream proposals into the review tray as they arrive rather than at the end of the run. **More valuable than before**: the editors are interactive, and a researcher waiting on a multi-minute assist run is now blocked at their desk rather than off doing something else. `ProgressTracker` and the polling infrastructure are already in place.

---

# Part 8 — Synthesis: what to build, in what order

## 8.1 The ten highest-leverage bets

Historical ranking by (methodological credibility gained) × (evidence in the literature) ÷ (effort), with dependencies noted. Completed entries remain to explain campaign sequencing; use `qualitative-coding-roadmap-audit.md` for the next dispatch queue rather than selecting the first unresolved row mechanically.

| Rank | Avenue | Why it wins |
|---|---|---|
| 1 | **D3 — Tabular export — RESOLVED** | Deterministic CSV/JSON, analysis-ready layouts, and project-bundle export shipped. Retained here to record why it was the first campaign priority. |
| 2 | **B1 (RESOLVED) + B3 — Coder identity and real IRR metrics** | B1 shipped: `coding_entries.coder`/`coder_model` records which entries are hand-coded vs. AI-proposed, rolled up per row. B3 (κ/α/AC1 with a per-code breakdown) is the remaining half — now genuinely unblocked rather than theoretically so. |
| 3 | **C2 — AI-assist provenance channel — RESOLVED** | Shipped as `artifact_assists`: model, prompts, and accepted/dismissed counts per assistant run, sourced from the job rather than the client. Closed GAP-4. TROUT-AI disclosure (C4) is no longer blocked on this. |
| 4 | **C3 + C4 — Methods appendix and TROUT-AI disclosure** | Nobody offers this, and the app's answer to T14 is now genuinely distinctive: "the AI proposed, a human accepted each item individually, here are the counts." Substantially a rendering task over data already held. |
| 5 | **G5 — Local/self-hosted model support** | A hard gate for IRB- and GDPR-constrained researchers. The single external-call seam survived two rewrites intact, so this stays contained. |
| 6 | **D1 — REFI-QDA codebook interop** | Turns "switch to us" into "fits your workflow." The codebook's structured, rename-proof model is most of the way to `.qdc` shape already. |
| 7 | **A6 — Saturation tracking** | Nearly free, and *cheaper than when first proposed*: the codebook editor already distinguishes novel proposals from already-covered ones on every run, which is the whole measurement. No competitor does it. |
| 8 | **B8 — DSL-corrected estimates** | Still the most genuinely novel capability on the list. Makes quantitative claims from AI-coded data publishable. The editors now generate the human-verified subsample it depends on as a by-product of ordinary use. Needs B7. |
| 9 | **F1 — Teams** | The single-researcher workflow is now good; nearly everything left in Theme B and C8 is blocked on the absence of a second user rather than on missing analytic machinery. |
| 10 | **G2 — Quote traceability checker** | A documented ethical failure with no market equivalent, directly on-point for a Reddit tool with sensitive-community sample data in the repo. Natural home is the quote bank (E6). |

## 8.2 A phased sequence

**Completed foundation — "Let the work out, and say who did it."** D3 export, C2 assist provenance, E1 coverage, job accounting/partial semantics, and the corrected comparison architecture have shipped. The remaining foundation work is I4 (model-run snapshots) and C1 (audit-trail rollup).

**Phase 2 — "Measure it" (≈ 6–10 weeks).** *Goal: the tool produces numbers, not just artifacts.*
B1 (coder identity) → B2 (blind double-coding) → B3 (IRR metrics) → A6 (saturation) → B9 (confidence-ordered review tray) → A4 (reflexivity).
*Outcome:* the full rigor apparatus for codebook-based analysis, on top of a human-in-the-loop workflow that already exists.

**Phase 3 — "Publishable and portable" (≈ 6–10 weeks).**
C3 (methods appendix) → C4 (TROUT-AI) → C5 (AI disclosure) → D1 (`.qdc`) → D2 (`.qdpx`) → C6 (repro bundle) → B7/B8 (gold sets, DSL) → G5 (local models).
*Outcome:* output that clears journal review, and interoperability with the tools reviewers' co-authors already use.

**Phase 4 — "Team and scale."**
F1 (teams) → F2–F5 (assignment, discussion, debriefing, calibration) → I1/I2 (durable, resumable jobs) → A1 (second-cycle themes) → E2/E3 (co-occurrence, crosstabs).

**Phase 5 — "New markets."**
D4 (generic text ingest — the biggest market lever) → H3/H4 (screening, policy consultations) → H2 (teaching) → H7 (institutional deployment) → H9 (publish a validation study).

## 8.3 The strategic thesis in one paragraph

**Updated.** The app now combines verified quotes, version and AI-assist provenance, an architecturally enforced human-in-the-loop, deterministic native exports, coverage reporting, and an honest separation between structural history comparison and LLM interpretation across artifacts. That is a stronger position than either "all comparison must be computed" or "let the model narrate everything." What remains is methodological validation and publication reporting: no inter-coder reliability engine, saturation report, methods/disclosure generator, REFI-QDA exchange, or second user. Those gaps now matter more than adding another general-purpose AI analysis surface.

## 8.4 What *not* to build

- **Don't chase Dovetail on transcription/repository polish.** Well-funded, crowded, and orthogonal to the defensible advantage.
- **The `origin=edited` decision was correctly left alone when GAP-4 was fixed.** Overloading `origin`/`model` to mean "AI helped" would have destroyed their audit value. `artifact_assists` (C2) and `coding_entries.coder` (B1) are the separate channels that closed the gap instead — a worked example, now shipped, of the principle this bullet originally warned about.
- **Don't confuse LLM interpretation with deterministic evidence.** Keep structural codebook/coding comparison in version history. Keep cross-artifact LLM comparison stored, viewable, exportable, and clearly labeled; never present its narrative as κ/α/AC1, a structural diff, or an objective match score.
- **Don't impose IRR universally.** For reflexive TA it is a category error; Braun & Clarke are explicit. Make it a per-tradition option (A9).
- **Don't market full automation** — and note the app is now architecturally incapable of it, which is the *better* story. Every study reviewed here concludes that LLMs should augment rather than replace; the editors embody that correctly. Lead with it.
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
