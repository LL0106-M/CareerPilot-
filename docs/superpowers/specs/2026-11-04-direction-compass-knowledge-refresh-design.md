# Direction-to-Compass and Knowledge Refresh Design

## Intent

When a user states a concrete application direction such as “我想要投递京东技术产品经理的岗位”, CareerPilot must treat it as an explicit career direction rather than a generic question. The completed turn should make the direction visible in Compass and start a traceable background collection of current job evidence for that company and role.

## Current failure and root cause

- The rule interpreter sees `岗位/投递` but `投递` is not a discovery marker, so the message falls through to `general_question`.
- The retrieval router therefore emits no jobs, web, or career-knowledge route and exposes no retrieval tool.
- The memory write gate does not admit this phrasing as a durable goal.
- Compass only reads `hypothesis` memories from the dashboard. It does not project explicit goal memories, and Dreaming is triggered only by reviews or career milestones.
- The RAG store has a working job ingestion pipeline and online search provider, but no persistent collection job is created from a direction signal.

## Desired behavior

For a clear statement containing application commitment, a company/organization target, and a role target:

1. Classify the turn as `job_discovery`, with a secondary durable direction signal.
2. Save the user-authored direction as an active `goal` memory with the current run as evidence.
3. Project explicit direction goals into Compass as **明确方向**. They are already user-confirmed; they must not be presented as an inferred hypothesis.
4. Create or reuse a persistent background knowledge-collection job keyed by normalized company + role + recruiting constraints.
5. Search current sources after the response succeeds. Prefer official recruitment sources, preserve URLs and observed timestamps, and never invent missing JD fields.
6. Store official, sufficiently parsed jobs as structured job records. Store incomplete or non-official results separately as unverified source leads.
7. Expose collection state (`queued`, `collecting`, `completed`, `partial`, `failed`) to the chat result and Jobs page so “started collecting” is observable.
8. Deduplicate repeated direction statements and refresh existing evidence instead of creating duplicate Compass cards or concurrent jobs.
9. Once a confirmed Compass direction enters Journey, create two additional bounded collection jobs: historical interview questions/experience and direction-specific learning resources.

## Approaches considered

### Model-decided tool call

Keep the current tool and rely on the model to set `save_to_library=true`. This is small but non-deterministic and already failed for the reported wording. Rejected.

### Synchronous retrieval and ingestion

Block the chat response until current sources are searched and stored. This gives immediate results but makes normal conversation depend on network latency and external failures. Rejected.

### Persistent background collection job — selected

Deterministically recognize a direction, commit the goal after a successful turn, enqueue an owner-scoped collection job, and process it in the background. The conversation remains responsive, jobs survive transient failures, and the UI can show progress. Selected by the user.

## Data and lifecycle

### Direction signal

A `DirectionSignal` contains the original statement, normalized company target, normalized role target, optional location/recruiting constraints, and confidence. Phase one uses deterministic commitment/job markers and slot extraction; ambiguous messages remain ordinary exploration and do not auto-collect.

### Compass projection

Compass receives two separately labelled collections:

- `directions`: active goal memories explicitly stated by the user.
- `hypotheses`: candidate or active hypotheses inferred by Dreaming.

The UI may display both in the same carousel but must label their origin and must not ask the user to reconfirm an explicit direction. Existing hypothesis confirmation and verification actions remain unchanged.

### Compass to Journey

A direction entering Compass does not create a Journey. Compass first preserves the confirmed direction, then offers an explicit “开始航程” action. Only the user's confirmation creates or reuses the Journey. The Journey is the preparation boundary: creating it triggers preparation collection, while merely discussing or saving a direction does not.

The generated Journey begins with a small, editable route rather than a large task dump:

1. Review the current role profile and verified openings.
2. Review historical interview questions and interview-experience evidence.
3. Use selected learning resources to close the most relevant preparation gaps.

Every generated task references the direction memory ID and the collection jobs that support it.

### Collection jobs

The RAG database gains a persistent collection-job table containing owner, normalized query key, direction memory ID, query, company, role, constraints, status, attempts, timestamps, summary counts, and a bounded error code. Only one active job exists per owner/query key.

Jobs are enqueued only after a non-failed assistant run, matching the memory commit boundary. A background processor claims jobs atomically and performs bounded online search and ingestion. Retrying is idempotent.

Collection jobs have one of three purposes:

- `job_opportunity`: current openings and official JD evidence; starts when the direction is confirmed in Compass.
- `interview_archive`: historical questions and interview-experience evidence for the company/role; starts when the direction enters Journey.
- `learning_resource`: courses, guides, cases, papers, and official technical/product material relevant to the direction; starts when the direction enters Journey.

These purposes use separate deduplication keys and terminal counts so one failed source type does not hide successful results from another.

## Knowledge-base information architecture

The current broad `preparation` bucket is split. The primary knowledge navigation becomes:

1. **个人资料** — private, owner-scoped resumes, portfolios, notes, and uploads.
2. **岗位信息** — current structured opportunities plus unverified job-source leads.
3. **往年题目** — historical interview questions and 面经, structured by company, role, year, round, topic, source, and confidence.
4. **学习资源** — courses, guides, cases, papers, and technical/product references, structured by topic, format, publisher, level, and linked direction.

`往年题目` and `学习资源` are different evidence domains. A document cannot silently move between them merely because both are used for preparation.

### Historical interview evidence

Historical questions are never presented as guaranteed future questions. Each item keeps company, role family, interview round when known, observed year/date, source URL, source level, excerpt, and verification status. Official or first-party material receives higher trust; anonymous experience posts remain explicitly labelled as experience reports.

Repeated questions may be clustered by semantic similarity, but the product retains individual sources and does not fabricate a canonical wording or model answer.

### Learning resources

Learning-resource collection is driven by the confirmed company/role direction and, when available, gaps observed between JD requirements and user evidence. Phase one can use the direction alone; it must not claim a personal skill gap without supporting user evidence.

Generic documents such as GraphRAG papers remain searchable learning resources only when their topic is relevant. They no longer occupy the featured preparation position merely because they were recently ingested.

### RAG scopes and domains

Replace the single preparation scope with distinct scopes while retaining a compatibility route during migration:

- `jobs` → `job_opportunity`
- `interview_archive` → `interview_question`, `interview_experience`
- `learning` → `learning_resource`, plus curated domain knowledge when relevant
- `personal` → owner-scoped personal material

Existing `preparation_material`, `domain_knowledge`, and `ai_frontier` documents are migrated or projected into `learning_resource`; they are never reclassified as interview evidence without explicit metadata.

### Source trust

- Official company recruitment pages: eligible for structured active job records when required fields can be extracted.
- Authorized recruitment pages: eligible with provenance and explicit source level.
- Aggregators, social posts, or incomplete search snippets: stored only as `unverified_lead`/collected sources.
- Missing location, deadline, requirements, or active status remain unknown; the system must not fill them from model inference.
- Every record keeps source URL and verification time. Existing freshness rules continue to govern retrieval.

## Product feedback

The completed chat response includes a compact deterministic system event such as “已把‘京东技术产品经理’加入罗盘，并开始收集岗位信息”. This acknowledgement is product state, not model-generated evidence.

Compass shows the new explicit direction immediately after the completed turn. The Jobs page shows an active collection card and refreshes/polls until terminal state, then separates verified jobs from leads requiring verification.

Journey shows collection progress beside the relevant preparation step. Knowledge navigation exposes separate `往年题目` and `学习资源` pages. Each page shows which Compass/Journey direction caused collection, when sources were checked, and whether an item is verified or only a lead.

## Error handling

- Goal/Compass persistence and job enqueue are transactional from the product perspective: if enqueue cannot be recorded, the goal remains but the response reports collection unavailable and offers retry.
- External search failure never removes the direction.
- Partial results remain visible with their trust level.
- Repeated messages reuse the existing direction and collection job.
- Failed or empty assistant runs do not save the direction or enqueue collection.

## Scope

### Included

- Direction classification and extraction for explicit company-role application statements.
- Active goal memory and Compass projection.
- Persistent background collection job, status API, and automatic processing.
- Verified/unverified source separation using the existing RAG and ingestion architecture.
- Chat, Compass, and Jobs-page feedback.
- User-confirmed Journey creation/reuse from a confirmed Compass direction.
- Separate historical-interview and learning-resource domains, APIs, pages, and collection jobs.
- Migration/compatibility handling for existing preparation documents.
- Tests across intent, post-turn lifecycle, persistence, API, and UI.

### Not included

- Continuous crawling of every employer without a user direction.
- Automated job applications.
- Generating model answers and presenting them as historical interview evidence.
- Treating search summaries as verified JDs.
- Replacing the existing RAG store or enabling MemOS as a knowledge authority.

## Acceptance criteria

Given “我想要投递京东技术产品经理的岗位” and a successful assistant response:

- Intent is not `general_question`; jobs and current web evidence are routed.
- One active explicit goal appears in Compass as a confirmed direction.
- One persistent collection job exists for the normalized JD technical-product query.
- No Journey exists until the user confirms “开始航程”; that confirmation creates exactly one Journey for the direction.
- Journey creation enqueues separate historical-interview and learning-resource jobs.
- Historical questions and learning resources appear in separate knowledge sections and retain source/trust metadata.
- The response exposes that Compass update and collection have started.
- Official structured results appear as jobs; incomplete results appear only under unverified sources.
- Repeating the message creates neither duplicate direction nor duplicate active job.
- A failed assistant response creates neither direction nor collection job.
