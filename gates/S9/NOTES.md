# Notes for gate S9 (power and tier table)

- **The proxy-kernel cluster counts are optimistic** (owner, 2026-11-01). The difficulty simulation (D18) gave 2–11
  clusters per model for 80% power. It contains none of the following variance sources:
  - the between-server-start shift (D14; S4 measures it);
  - variance across wordings (the brief's pre-registered prompt-sensitivity factor);
  - call-level noise of real models (S4);
  - the spread across graphs at N = 100 (S1 measured the spread at N = 20,000; `inputs_from_S1.yaml`).
- **Tier sizes come from measured kernels** (S3–S5, the S8 pilot), with every source above included as its own
  variance component. The proxy numbers rank difficulty settings; they never size the study.
- **The informed-status split (D19) is secondary**, with no power target. S9 powers only the two confirmatory
  contrasts.
