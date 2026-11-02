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

- **S4 inputs (2026-11-02, `gates/S4/results/s4_variance_components.json`).** Per model and wording: start-offset
  variance (≤ 1e-4 nats² everywhere) and probe × start variance (W3: Llama 0.0026, Qwen3.5-9B 0.0033, Qwen3.5-27B
  0.0027, Gemma-3-27B 0.020, Gemma-2-9B 0 nats²). Starts are discrete states (`s4_start_states.json`), not continuous
  drift. The D14 tripwire fired (Gemma-3-27B), so the simulation blocks every analysis by start. Presentation effects
  (letter and option order; large for both Gemma models) are in `s4_summary.json` and add call-level variance even
  though the balanced design cancels their mean.
