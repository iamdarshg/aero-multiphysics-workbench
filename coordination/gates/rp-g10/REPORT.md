# RP-G10 — Adversarial review of the research paper: **PARTIAL**

Repo: `E:\engineering-portfolio-audit\repos\research-paper`, branch `verify/fable-c2`, HEAD `a56511a`.
Paper source read: `paper/main.tex`, `paper/sections/{introduction,results-and-discussion,conclusion,related-work}.tex`,
plus the repo's own claim docs: `paper/FINAL_RUN_GATES.md`, `paper/SCIENTIFIC_GATE_STATUS.md`,
`paper/CLAIMS_EVIDENCE_MATRIX.md`, `paper/REVIEWER_KIT.md`, `README.md`, `tests/test_diversity_novelty_gate.py`.

Measured ground truth used (not re-derived here): RP-G1 (D3 576/576, **35 distinct = 9.9 %**; A2/B2 collapse),
RP-G2 (held-out GT novelty **0.000508**, 68/96 exactly 0), RP-G4 (GT 0.433 vs decoder-on-true-latents 0.006),
RP-G5 (`E:\engineering-portfolio-audit\evidence\notrun-gates\rp-g5\` — `new_gate_pass=false`,
`distinct_array_count=1`, `novel_voxel_fraction_mean=0.0`, bit-identical across 2 seeds × 96 conditions).

Supplemental run for this review: the gate's own test suite —
`tests/test_diversity_novelty_gate.py` **5 passed** (`raw\rp_g5_gate_tests.log`) — confirms the gate and its
negative controls are wired as the paper describes. No training run was started (free RAM ≈ 0.5 GB).

---

## 1. Claim table

| # | Claim (quoted) | Where | Repo's own evidence | Verdict |
|---|---|---|---|---|
| C1 | "generated samples pass 45/45 under both the shipped four-step sampler and a teacher-DDIM sampler, and the artifacts re-screen as 45/45" | `conclusion.tex:3`; `main.tex:32`; `results-and-discussion.tex:249-250,256-257` | RP-G5 on the only saved checkpoint: `old_gate_pass_rate = 0.0`, `new_gate_pass = false`, 1 distinct array. This is a **different checkpoint/arm** from the paper's 45/45 (measured host, no saved `final_monitored_model.pt` for it). | **UNVERIFIABLE** |
| C2 | "the 45 draws contain five near-identical voxel arrays" | `main.tex:32`; `conclusion.tex:3`; `results-and-discussion.tex:265` | `FINAL_RUN_GATES.md:24` and `SCIENTIFIC_GATE_STATUS.md:55` say **2 distinct among 45**. RP-G1 says the strongest arm is **35/576 (9.9 %)**. Internal inconsistency; no artifact for 5. | **UNSUPPORTED / contradictory internally** |
| C3 | "every emitted voxel is present in the training corpus" / "zero novel voxels" | `main.tex:32`; `results-and-discussion.tex:275`; `conclusion.tex:3` | Consistent with RP-G2 (0.000508) and RP-G5 (0.0), though neither figure (0.000508, 0.0) appears in the paper or any repo file. | **SUPPORTED direction, figure UNVERIFIABLE** |
| C4 | "a model-free constant array passes the same screen on every held-out record" | `main.tex:32`; `results-and-discussion.tex:276-278`; `conclusion.tex:3` | Reproduced here (`raw\rp_g5_negative_controls.log`): `constant_union old_gate_pass=True`; paper's "covers 98.6–99.4 % of every held-out record" is self-reported, no artifact. | **SUPPORTED (qualitative)** |
| C5 | "The paper therefore demonstrates that the current heuristic gate is satisfiable by a training-hull emitter; it does not demonstrate novel, conditioned, or diverse generation" | `conclusion.tex:3`; `results-and-discussion.tex:279` | Matches frozen gate code (`scripts/diversity_novelty_gate.py:21` `novelty_min_fraction 0.01`) and RP-G2/RP-G5. | **SUPPORTED** |
| C6 | "reconstruction now passes 9/9" + "the decisive change was decoder supervision density" | `conclusion.tex:3`; `results-and-discussion.tex:256,262` | Direction agrees with RP-G4 ("decoder is the bottleneck"), but RP-G4's measured magnitudes (0.433 vs 0.006) appear nowhere in the paper; the 9/9 itself has no committed artifact. | **PARTIALLY SUPPORTED / UNVERIFIABLE figures** |
| C7 | Four bounded contributions, none of them a valid generative contribution | `introduction.tex:7-13` | Consistent with RP-G1/G2/G3/G5. | **SUPPORTED** |
| C8 | "Aerodynamic optimization, structural viability, manufacturing validity, and physical-performance claims remain blocked" | `main.tex:32`; `conclusion.tex:5,7`; `FINAL_RUN_GATES.md` claim table | README open: "hostile review found that it must be framed as a negative-results/reproducibility paper"; every claim gate reads "claim evidence blocked". | **SUPPORTED** |
| C9 | "The corrected frozen corpus meets the 5 % gate on 1/16 sonicFoam and 0/14 simpleFoam rows" | `main.tex:32`; `conclusion.tex:5`; `results-and-discussion.tex:383-388` | Internally consistent across paper + `FINAL_RUN_GATES.md` addendum; raw tables not committed in this checkout. | **SUPPORTED / UNVERIFIABLE raw** |
| C10 | "The n=12 condition-response sweep is non-significant" | `conclusion.tex:5`; `main.tex:32` | Matches `FINAL_RUN_GATES.md` addendum ("n=12, non-significant") and `CLAIMS_EVIDENCE_MATRIX.md` C12. | **SUPPORTED** |
| C11 | Cited evidence paths `build/recovery_2026-11-05/PREREGISTERED_PROTOCOL.md` and `evidence/research-paper-publish/GENERATOR_RECOVERY_2026-11-05.md` | `results-and-discussion.tex:223`; `FINAL_RUN_GATES.md:38`; `SCIENTIFIC_GATE_STATUS.md:43` | **Neither path exists** in the repo (`build/` absent; no `evidence/` dir; no `PREREGISTERED*` file anywhere). | **BROKEN CITATION** |
| C12 | `45 epochs, latent 16` recovery checkpoint | `results-and-discussion.tex:253-254` | Only committed checkpoint (`rp-g1/run-w0p5-14ep/final_monitored_model.pt`) is **14 epochs, latent_dim 192** (`history.json:7,10`), i.e. the `w=0.0` collapse family. | **UNVERIFIABLE / misattributable** |

## 2. The four specific questions

**Q1 — does the paper claim a valid *generative* contribution while novelty is 0.0005 and the best arm is 9.9 % unique?**
**No, and it is unusually explicit about not doing so.** The abstract (`main.tex:32`), the results
(`results-and-discussion.tex:262-283`) and the conclusion (`conclusion.tex:3,7`) all state that the gate is
satisfiable by a training-hull emitter and that novel/conditioned/diverse generation is **not** demonstrated.
The strongest stated contribution (`introduction.tex:9-12`) is the *repair + measurement discipline*, not a
generator. RP-G11's reading ("any claim of a valid generative contribution is unsupported") is about the
`FINAL_RUN_GATES.md:40` phrase "**Literal form passed**", not about the paper, which frames it as literal-only.

**Q2 — is occupancy/validity presented in a way that hides the collapse?**
Partially. The paper never quotes a bare "576/576"; it uses 45/45 **and** immediately states five distinct
arrays plus zero novelty (`results-and-discussion.tex:265,275`). But the 45/45 → five-array framing is
*more favourably stated than either source of truth*: `FINAL_RUN_GATES.md:24` says 2 distinct in 45, and
RP-G1/RP-G3 report 9.9 % unique at 576 draws. The collapse is disclosed; its magnitude is under-reported and
internally inconsistent.

**Q3 — does the paper distinguish "the decoder works" from "the generator produces novel designs"?**
Yes on the structure (three arms: ground truth / reconstruction-latent-given / generation,
`results-and-discussion.tex:229-233`), and §"decisive change was decoder supervision density"
(`:258`) aligns with RP-G4. What it fails to do is report RP-G4's actual diagnostic (GT 0.433 vs
decoder-on-true-latents 0.006) — the one number that most cleanly separates decoder capability from
generative capability. The distinction is asserted, not evidenced with the committed measurement.

**Q4 — any number quoted without a traceable run behind it?**
Yes, several: the whole 9/9 → 45/45 recovery (`build/recovery_2026-11-05/` absent); the two protocol/evidence
paths in C11; `45 epochs, latent 16`; "covers 98.6–99.4 % of every held-out record"; and the digits
`0.000508` / `9.9 %` never appear in the paper at all, so the paper's qualitative statements cannot be
checked against the harness that measured them.

## 3. Overall verdict: **PARTIAL**

- **No headline claim is contradicted** by the repo's own evidence. Every "we did not / cannot claim X"
  statement is corroborated: novelty ≈ 0 (RP-G2/RP-G5), 9.9 % unique (RP-G1), decoder bottleneck (RP-G4),
  gate passes a constant (RP-G5). The paper is a negative-results/reproducibility paper and says so.
- **Several headline claims are UNVERIFIABLE** because the run behind them was never committed — including
  the single strongest quantitative claim (45/45). A reviewer cannot reproduce it from this checkout.
- **One set of quantitative claims is internally inconsistent** (five distinct arrays vs the repo's two)
  and one is a broken citation. These are reporting defects that should be fixed before any submission, and
  they are why this is not PASS.

Suggested gate wording: *"RP-G10 PARTIAL — claims are directionally supported and no claim overstates the
generator, but the headline 45/45 recovery is unverifiable in-repo (no committed `build/recovery_2026-11-05/`),
the diversity figure conflicts with the repo's own 2-distinct record, and RP-G4's decoder diagnostic is
omitted."*

## 4. Evidence files
- `evidence\notrun-gates\raw\rp_g10_claim_check.py` / `.log` — claim-by-claim citation extraction + overclaim scan.
- `evidence\notrun-gates\raw\rp_g5_negative_controls.py` / `.log` — independent reproduction of the constant/plus/three-box controls.
- `evidence\notrun-gates\raw\rp_g5_gate_tests.log` — gate test suite, 5 passed.