"""Original research hypotheses and proposed tests, not validated purchase demand.

Primary sources were inspected on 2026-11-16. Old benchmark publications are not
presented as new 35-day releases. Thresholds below are proposed pilot contracts,
not measurements or claims of feasibility. No source text is copied verbatim.
"""
from .core import PROBLEM_SCHEMA,sha

# id, title, beneficiary, outcome, blocker, tags, primary source, test, value driver,
# delivery unit, buyer question, reusable asset, access, criterion definitions.
NEW = [
 ('verified-gpu-kernel-production','Correct, workload-level GPU acceleration',
  'Private inference providers and AI infrastructure teams',
  'Deliver a deployable kernel replacement that reduces total workload cost without changing numerical behavior or peak memory commitments.',
  'A fast isolated kernel can fail at full-model integration, unusual shapes, numerical accuracy or memory usage.',
  ['gpu-kernels','cost-reduction','software-assurance'],
  'https://proceedings.mlr.press/v267/ouyang25a.html',
  'Freeze customer-representative shapes and device configuration; compare vendor libraries and compiled PyTorch, including warmup, retries, memory and total application latency.',
  'A buyer could pay from independently measured compute savings; net savings must exceed integration and support cost.',
  'One versioned workload/device optimization with regression suite',
  'Which workload, hardware, precision, monthly usage and minimum net saving would justify a paid deployment?',
  'Device-specific benchmark harness and numerical equivalence tests',
  'AUTHORIZED_COMPUTE_REQUIRED',
  [('heldout-correctness-bps','>=',10000,'basis points','Check exact or declared-tolerance outputs on unseen shapes and seeds.'),
   ('application-speedup-bps','>=',12000,'basis points','Compare end-to-end median and tail latency with the fastest eligible incumbent; 1.2x is a proposed pilot target.')]),
 ('research-reproduction-to-service','Research results to reproducible working systems',
  'Private AI laboratories and technical product teams evaluating research adoption',
  'Deliver a reproducible implementation of a selected research result with executed experiments, traceable dependencies and a documented deployment boundary.',
  'Understanding a paper, filling implementation gaps and reproducing experiments remain separate from producing plausible code.',
  ['research-replication','long-horizon-agents','software-assurance'],
  'https://openai.com/index/paperbench/',
  'Choose an authorized paper and independently written rubric; hold out evaluation seeds and compare an expert using conventional software and an expert using frontier AI.',
  'Reduce the cost and delay of evaluating an R&D investment; a useful implementation can support subsequent products.',
  'One independently reproducible paper-to-system package',
  'Which result changes a funded product decision, and what reproduction evidence would make the package worth purchasing?',
  'Reusable experiment runner, dependency map and replication rubric',
  'AUTHORIZED_COMPUTE_REQUIRED',
  [('critical-rubric-items-passed-bps','>=',10000,'basis points','All predeclared critical requirements must pass independent rerun.'),
   ('reproducible-runs','>=',3,'runs','Repeat with three prospectively selected seeds; three is a proposed pilot scope.')]),
 ('engineering-document-to-data','Engineering documents to traceable machine-usable data',
  'Private manufacturers and engineering software vendors',
  'Convert authorized complex specifications into structured tables and requirements with source coordinates, units and explicit abstention.',
  'Mixed tables, diagrams, equations and damaged pages can yield convincing but incorrect facts that contaminate downstream engineering.',
  ['document-understanding','multimodal-reasoning','data-provenance'],
  'https://openaccess.thecvf.com/content/CVPR2025/html/Ouyang_OmniDocBench_Benchmarking_Diverse_PDF_Document_Parsing_with_Comprehensive_Annotations_CVPR_2025_paper.html',
  'Construct an authorized unseen document set with independently labeled fields and unit checks; compare conventional extraction and qualified specialist review. Do not redistribute research-only datasets.',
  'Replace repeated manual transcription while preserving traceability; value depends on error cost and usable coverage, not page count alone.',
  'One source-linked structured specification corpus',
  'Which fields are critical, what error tolerance is acceptable, and what does the current complete review process cost?',
  'Schema, unit checker and provenance-linked evaluation set',
  'LOCAL_RESEARCH',
  [('critical-false-assertions','=',0,'errors','Abstain instead of guessing on unsupported critical fields.'),
   ('usable-field-coverage-bps','>=',9500,'basis points','Proposed pilot coverage over a frozen independently labeled set; must include abstentions.')]),
 ('accessible-application-workflows','Accessible complex application workflows with regression protection',
  'Private SaaS vendors and digital-commerce operators',
  'Deliver a scoped repair to a complete interactive workflow, together with repeatable keyboard and assistive-technology acceptance evidence.',
  'Automated scans do not establish complete accessibility; state transitions, focus management and actual interaction can remain broken.',
  ['computer-use','accessibility','software-assurance'],
  'https://www.w3.org/WAI/test-evaluate/',
  'Freeze one complete permitted workflow; compare conventional auditing and specialist remediation, including independently specified keyboard and assistive-technology scenarios. Do not claim site-wide conformance from a finite test.',
  'Remove a documented usability barrier and reduce recurring remediation effort; commercial and legal value require separate validation.',
  'One repaired workflow with scoped acceptance and regression tests',
  'Which workflow is blocked, which users and devices must it support, and who can accept the scoped result?',
  'Interaction-state regression harness and reusable component fixes',
  'EXTERNAL_VALIDATION_REQUIRED',
  [('critical-interaction-failures','=',0,'failures','All agreed keyboard, focus and assistive-technology scenarios must pass.'),
   ('functional-regressions','=',0,'failures','Existing functional tests must still pass; separate from conformance certification.')]),
 ('industrial-site-screening','Evidence-backed industrial site screening',
  'Private renewable-energy developers, logistics operators and industrial site teams',
  'Produce a ranked shortlist of sites with reproducible geospatial evidence, uncertainty and clearly identified missing field or commercial checks.',
  'Remote sensing can support screening but does not establish land rights, grid access, permits, subsurface conditions or project economics.',
  ['geospatial-reasoning','multimodal-reasoning','physical-validation'],
  'https://deepmind.google/blog/alphaearth-foundations-helps-map-our-planet-in-unprecedented-detail/',
  'Freeze permitted public layers and a held-out labeled region; compare established GIS analysis and a competent specialist. Verify rights and site-specific facts outside the AI screen before any transaction.',
  'Reduce wasted diligence on unsuitable sites while retaining high-quality candidates; screening is not an investment recommendation or acquisition authority.',
  'One reproducible regional shortlist with source lineage',
  'What screening constraints, shortlist acceptance criteria and cost of false positives make this output worth buying?',
  'Versioned feature pipeline, label set and uncertainty audit',
  'EXTERNAL_VALIDATION_REQUIRED',
  [('known-disqualifying-constraints-missed','=',0,'errors','Check the frozen constraint set; mark unavailable facts unknown.'),
   ('heldout-recall-bps','>=',9000,'basis points','Proposed recall target measured against the preregistered held-out labels.')]),
 ('accepted-software-repair','Complex software repairs with outcome-based acceptance',
  'Private software product teams with reproducible high-impact defects',
  'Deliver a repair accepted against unseen end-to-end tests, regression checks and agreed support conditions.',
  'A patch that fits visible examples can fail hidden behavior, integration and maintenance requirements.',
  ['software-repair','long-horizon-agents','software-assurance'],
  'https://openai.com/index/swe-lancer/',
  'Freeze a permitted issue, reproduction and hidden end-to-end tests; benchmark direct developer delivery, current coding agents and no purchase under equal terms.',
  'Paid freelance engineering tasks are evidence of a market category, not a purchase commitment to ALPHA; value depends on the specific unresolved defect.',
  'One independently accepted repair plus bounded support',
  'Which defect is funded, what exact tests accept its repair, and what is the price ceiling and support obligation?',
  'Reproduction environment and reusable regression cases',
  'LOCAL_RESEARCH',
  [('heldout-end-to-end-pass-bps','>=',10000,'basis points','Execute all frozen acceptance scenarios without exposing expected outputs to construction.'),
   ('new-critical-regressions','=',0,'failures','Compare the repaired system against both previous behavior and the agreed corrected behavior.')]),
]

EXISTING = {
 'compiled-crypto-assurance':(
  'Reduce specialist effort per correctly scoped machine-code assurance deliverable; a proof of the wrong statement has no promised value.',
  'One pinned binary/specification proof package',
  'Which binary and exact theorem would you purchase assurance for, under what trusted assumptions and quoted price?',
  'Approved specifications and proof-replay/mutation harness','LOCAL_RESEARCH',
  [('invalid-proofs-accepted','=',0,'failures','Independent checker rejects all seeded invalid proofs.'),('seeded-bugs-detected-bps','>=',10000,'basis points','Replay the agreed known-bug mutation set, not a claim about unknown bugs.')]),
 'private-inference-provenance':(
  'Assurance buyers may pay for attributable inference; proof generation, verification and integration cost must fit that premium.',
  'One committed-model receipt integration',
  'Which trust assumption cannot a signature or TEE satisfy, and what premium per verified request is acceptable?',
  'Model-bound verification gateway and substitution tests','AUTHORIZED_COMPUTE_REQUIRED',
  [('mutated-receipts-accepted','=',0,'failures','Reject changed commitments, outputs and verification keys.'),('genuine-receipts-accepted-bps','>=',10000,'basis points','Replay the agreed genuine proof set with pinned supported inference settings.')]),
 'enterprise-modernization-migrations':(
  'Avoid recurring legacy maintenance and enable product changes; migration and rollback risk must be priced into complete delivery.',
  'One behavior-preserving service migration',
  'What complete service behavior and rollback guarantee must survive, and what is the approved migration budget?',
  'Compatibility oracle, dependency graph and migration/rollback playbook','LOCAL_RESEARCH',
  [('critical-contract-regressions','=',0,'failures','Hold out contract and security tests from the builder.'),('rollback-recoveries-bps','>=',10000,'basis points','Recover each predeclared interrupted rollout in the permitted sandbox.')]),
 'enterprise-sop-verifiable-agents':(
  'Sell completed procedures rather than tool calls; usable value requires correct exceptions, policy compliance and measured support cost.',
  'One accepted procedure instance with audit evidence',
  'Which procedure, exception classes, authorizations and accepted-result price could support recurring purchase?',
  'Procedure state machine, independent state checks and recovery cases','LOCAL_RESEARCH',
  [('unauthorized-actions','=',0,'violations','Use a permitted sandbox with denial and conflicting-instruction cases.'),('heldout-procedure-success-bps','>=',9900,'basis points','Proposed pilot target; finite tests do not prove the production failure rate.')]),
 'computer-use-business-workcells':(
  'Eliminate repeated cross-application handling where APIs or ordinary RPA do not already win on full cost.',
  'One verified cross-application outcome',
  'Which cross-application outcome lacks a cheaper complete API/RPA route and has explicit state-change permission?',
  'Application-state oracle and idempotent recovery actions','LOCAL_RESEARCH',
  [('duplicate-side-effects','=',0,'events','Repeat each interrupted step and check the resulting state independently.'),('heldout-completions-bps','>=',9900,'basis points','Proposed finite pilot target including changed screens and refusals.')]),
 'electronic-design-to-bench':(
  'Shorten design-to-qualified-prototype iterations; board cost, failed revisions and independent bench work remain full costs.',
  'One low-risk subsystem with manufactured-test package',
  'What measured subsystem requirement and manufacturing budget would justify a paid prototype, and who controls the lab?',
  'Test fixture, bill of materials and validated design rules','EXTERNAL_VALIDATION_REQUIRED',
  [('critical-bench-failures','=',0,'failures','Independently measure all frozen electrical and thermal acceptance cases.'),('fault-tests-passed-bps','>=',10000,'basis points','Check only the agreed low-risk fault tests using authorized lab equipment.')]),
}


def additions():
    result=[]
    for row in NEW:
        ident,name,buyer,outcome,blocker,tags,url,test,*_=row
        result.append({'schema':PROBLEM_SCHEMA,'id':ident,'title':name,'beneficiary':buyer,
          'outcome':outcome,'acceptance':test,'blocker':blocker,'tags':tags,
          'demand':{'status':'PUBLIC_SIGNAL','basis':'Primary technical source supports investigation of the problem class; this proposed offer, price and customer demand remain unvalidated.',
                    'ceiling_microUSD':None,'deadline':None,'terms_sha256':None,'consent_verification':'NOT_VERIFIED'},
          'alternatives':[
            {'name':'Competent specialist','route':'Experienced human specialist using established domain software and independent acceptance.','unknowns':'Obtain a current complete quote and comparable evidence; no cost assumed here.'},
            {'name':'Human-plus-AI provider','route':'Qualified team using current frontier tools and existing reusable methods.','unknowns':'May already deliver the complete outcome; benchmark equal rights, resources and support.'},
            {'name':'No purchase','route':'Defer work or retain the current solution.','unknowns':'Quantify the buyer-approved cost of inaction instead of inventing demand.'}],
          'source_urls':[url],'next_test':test})
    return result


def briefs_for(problems):
    from .inventory import SCHEMA
    mapping=dict(EXISTING)
    mapping.update({row[0]:tuple(row[8:]) for row in NEW})
    briefs=[]
    for p in problems:
        if p['id'] not in mapping:continue
        value,unit,question,asset,access,criteria=mapping[p['id']]
        briefs.append({'schema':SCHEMA,'id':'brief-'+p['id']+'-v1',
          'problem_id':p['id'],'problem_sha256':sha(p),'assessed_on':'2026-11-16',
          'value_driver':value,'delivery_unit':unit,'buyer_question':question,
          'successor_asset':asset,'access':access,'source_urls':p['source_urls'],
          'criteria':[dict(zip(('metric','operator','target','unit','test'),c)) for c in criteria]})
    return briefs
