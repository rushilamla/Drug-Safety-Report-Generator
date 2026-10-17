# GenAR AI Engineering Challenge

## Overview

This project is a small prototype for generating a controlled, evidence-based pharmacovigilance report from an ICSR safety dataset.

Version 0 supports a PADER-style report for the supplied Bisoprolol dataset.

The design deliberately separates deterministic data analysis from AI-generated narrative so that the same analysis and evidence layer can later support other report types such as PSUR, PBRER, DSUR, or CSR through configuration rather than a complete rewrite.

---

## 1. What the system does

The system performs the following steps:

1. Loads the supplied ICSR dataset.
2. Normalizes patient age into years and age groups.
3. Identifies unique cases using `safetyreportid`.
4. Separates case-level analysis from reaction-level analysis.
5. Computes deterministic statistics using Python and pandas.
6. Builds a scoped evidence packet containing approved analysis results.
7. Sends the report configuration and evidence packet to Gemini.
8. Generates the report narrative.
9. Appends a deterministic case index and human-review status.
10. Saves the final report as `report_output.md`.

The raw dataset is never sent to the LLM.

---

## 2. Project structure

```text
genar-challenge/
│
├── data/
│   └── Bisoprolol_icsr_sample_1068rows.xlsx
│
├── prompts/
│   └── report_prompt.txt
│
├── src/
│   ├── main.py
│   └── data_exploration.ipynb
│
├── version1/
│   └── design.md
│
├── README.md
├── architecture.png
└── report_output.md
```

The supplied dataset is used locally during development but should not be included in the final submission ZIP.

---

## 3. How to run

### Requirements

Python 3.x with the following packages:

```bash
pip install pandas openpyxl google-genai tabulate
```

The Gemini API key is supplied through an environment variable.

### PowerShell

```powershell
$env:GEMINI_API_KEY="YOUR_API_KEY"
```

Then run from the project root:

```powershell
python src/main.py
```

The generated report is written to:

```text
report_output.md
```

---

## 4. Architecture

```text
                    Reporting Task
                         │
                         ▼
                  REPORT_CONFIG
                         │
                         ▼
Raw ICSR Data ──► Deterministic Analysis
                         │
                         ▼
                  Evidence Packet
                         │
                ┌────────┴────────┐
                │                 │
                ▼                 ▼
        Report Configuration     LLM
                                  │
                                  ▼
                         Generated Narrative
                                  │
                     ┌────────────┴────────────┐
                     ▼                         ▼
              Human Review                Case Index
                     │                         │
                     └────────────┬────────────┘
                                  ▼
                           report_output.md
```

The main architectural principle is:

**Python computes facts. The LLM communicates those facts.**

---

## 5. Deterministic code vs. AI

### Deterministic Python

Python is responsible for calculations that should be exact and reproducible:

- unique case counts
- serious/non-serious counts
- age normalization and age groups
- sex distribution
- geographic distribution
- reporter qualification
- reaction frequencies
- serious reaction frequencies
- outcome counts
- monthly case counts
- expedited/alert case counts
- data-quality checks
- case index generation

This prevents the LLM from doing arithmetic or inventing counts.

### AI / LLM

The LLM is responsible for:

- organizing the supplied evidence
- writing the narrative
- explaining numerical patterns in neutral language
- following the configured report structure

The LLM does not receive the raw dataset.

This split follows the challenge's grounding example, where deterministic analysis is performed in Python and the model receives an assembled evidence packet rather than the raw CSV.

---

## 6. Evidence packet and grounding

The deterministic analysis produces a Python dictionary containing approved results such as:

```text
total_cases
serious_cases
non_serious_cases
age_groups
sex
country
top_reactions
top_serious_reactions
outcomes
monthly_cases
alert_analysis
data_quality
```

This dictionary is serialized into JSON and inserted into the report prompt.

The model therefore receives a scoped evidence packet rather than the raw Excel data.

Example:

```text
Python:
total_cases = 1024
serious_cases = 1023
non_serious_cases = 1

        ↓

Evidence Packet

        ↓

LLM

        ↓

"1,024 cases were reported, of which
1,023 were classified as serious."
```

The number comes from Python rather than from model arithmetic.

The challenge specifically emphasizes that every generated numerical claim should be traceable to the deterministic analysis.

---

## 7. Why cases and reactions are treated separately

The dataset contains 1,068 rows but only 1,024 unique `safetyreportid` values.

Therefore:

- case-level statistics use unique `safetyreportid`
- reaction-level statistics use the source reaction field
- outcomes are handled separately

This prevents row counts from being incorrectly interpreted as case counts.

The supplied Starter Guide explicitly warns that 1,068 rows do not represent 1,068 cases and recommends consistent case-level versus reaction-level handling.

---

## 8. Data-quality handling

The source dataset contains six rows where the number of reaction values does not match the number of outcome values.

The system does not guess which outcome belongs to which reaction.

Instead, those reaction/outcome pairings are marked as unavailable and the number of affected rows is reported as a data-quality limitation.

This preserves the source information without inventing a relationship that is not supported by the data.

---

## 9. Age normalization

The dataset contains age values expressed in different units.

The system converts:

```text
year  → years
month → years / 12
week  → years / 52
day   → years / 365
```

The dataset also contains the age-unit value `800`. This value is not interpreted as a real age unit and is treated as unavailable for normalized age.

Age is then grouped into:

```text
<18
18–44
45–64
65–74
75+
Unknown
```

---

## 10. Report configuration

The system has a small report configuration:

```python
REPORT_CONFIG = {
    "report_type": "PADER",
    "product": "Bisoprolol",
    "required_sections": [...]
}
```

This is intentionally separate from the deterministic analysis code.

PADER is the first supported report type, not the definition of the whole system.

A future report configuration could specify a different:

- report type
- set of required sections
- evidence requirements
- generation instructions

The goal is to reuse the underlying analysis and evidence capabilities rather than create a separate code path for every report type.

The challenge explicitly frames the PADER as the entry point and asks how much of the system could survive future report types through configuration and data rather than new code paths.

---

## 11. Prompt and context design

It contains:

1. report configuration
2. generation rules
3. evidence and grounding rules
4. the deterministic evidence packet

The prompt explicitly instructs the model:

- to use only supplied evidence
- not to invent values
- not to recalculate statistics
- not to infer causality
- not to invent expectedness
- not to invent regulatory actions
- not to invent SOC information
- to state when required information is unavailable

The actual prompt is included in the submission rather than hidden inside the code.

### Prompt structure

The actual prompt is stored in `prompts/report_prompt.txt`.

Its structure is:

```text
REPORT CONFIGURATION
        ↓
generation and grounding rules
        ↓
EVIDENCE PACKET
        ↓
LLM generates only the configured report sections
```

Key instructions include:

```text
Use ONLY information present in the EVIDENCE PACKET and REPORT CONFIGURATION.

Do not invent numerical values, cases, reactions, outcomes,
dates, countries, or regulatory actions.

Do not recalculate numerical statistics.

Do not claim that an adverse event was caused by the product.

Do not infer expectedness unless the required reference
safety information is explicitly supplied.

If required information is unavailable, state that it
was not supplied instead of inventing it.
```

The complete prompt template is included separately in `prompts/report_prompt.txt`.

---

## 12. Human review

The generated report is marked:

```text
Status: Pending human review
```

The intended workflow is that a qualified reviewer checks the generated narrative against the deterministic analysis before the report is considered final.

This is important because a numerical observation should not automatically become a medical or regulatory conclusion.

The challenge explicitly requires a human-review point somewhere in the flow.

---

## 13. Current report limitations

The supplied dataset does not contain:

- product label / CCDS information
- MedDRA System Organ Class
- history of safety-related actions
- full clinical case narratives
- sufficient information for a complete expectedness assessment

Therefore the system explicitly reports those limitations rather than filling them with assumptions.

The Starter Guide specifically states that SOC-level analysis is unavailable from the supplied dataset and that expectedness is out of scope without the product label/CCDS.

The project is a prototype and is not intended to represent a production regulatory reporting system.

---

## 14. Evaluation approach

Version 0 uses deterministic analysis as the primary source of truth.

Before accepting a generated report, the following should be checked against the deterministic results:

- total case count
- serious/non-serious counts
- major reaction counts
- alert count
- reporting period
- required report sections
- case index presence
- unsupported regulatory or causal conclusions

For a larger-scale system, this could be automated by extracting claims from generated reports and matching them against the evidence packet across many generated reports.

---

## 15. Case index

The final report contains a deterministic case index generated by Python.

The index includes:

```text
Case ID
Reaction
Seriousness
Reporting Date
Country
Outcome
```

The purpose is traceability: a reviewer should be able to move from an aggregate observation back to individual case-level records.

This follows the Starter Guide's case-index requirement.

---

## 16. 15-Day / expedited cases

The dataset contains the field `fulfillexpeditecriteria`.

The system separately calculates:

```text
alert_cases
alert_serious_cases
alert_non_serious_cases
```

For this dataset, the resulting counts are:

```text
Alert cases: 1,023
Serious alert cases: 1,023
Non-serious alert cases: 0
```

The Starter Guide notes that 1,023 of the 1,024 cases meet the expedited criterion in this dataset.

Expectedness is not evaluated because the supplied product label/CCDS information is unavailable.

---

## 17. Why plain Python?

The dataset is small and the deterministic calculations are straightforward.

Plain Python and pandas make the workflow:

- easy to inspect
- easy to reproduce
- easy to debug
- easy to explain in a live technical session

A framework or multi-agent architecture was not added because it would not provide a clear benefit for Version 0.

The challenge explicitly states that frameworks and tool count are not what is being scored; the reasoning behind the design is more important.

---

## 18. Why use an LLM?

The LLM is useful for converting structured evidence into readable narrative and adapting that narrative to a configured report structure.

It is not used for:

- counting cases
- calculating frequencies
- deduplicating cases
- determining numerical trends
- constructing the case index

Those tasks remain deterministic.

---

## 19. Why not send the entire dataset to the LLM?

The challenge explicitly demonstrates a grounded pattern where Python performs the analysis and the model receives an assembled, scoped packet.

Sending the raw dataset directly to the model would make it harder to control arithmetic, trace claims, and explain where each number came from.

---

## 20. Future evolution beyond PADER

The reusable core is:

```text
data ingestion
      ↓
deterministic analyses
      ↓
evidence packet
      ↓
report configuration
      ↓
controlled LLM generation
      ↓
human review
```

To support PSUR, PBRER, DSUR, or CSR, the system should primarily add configuration describing:

- required sections
- required analyses
- required evidence
- report-specific generation instructions

Reusable analyses such as case counts, reactions, outcomes, demographics, and time trends can continue to serve multiple report types.

The long-term goal is therefore not a collection of independent report generators.

It is a reporting system that:

**takes a reporting task → gathers the appropriate evidence → reasons over that evidence → produces a controlled, traceable report.**

PADER is simply the first report type supported by Version 0.

---

## 21. Known Version 0 limitations

Version 0 intentionally remains small.

Current limitations include:

- only one report type is configured
- report-specific evidence dependencies are not yet represented as a full dependency graph
- human review is represented as a workflow state rather than an interactive approval UI
- automated evaluation is basic rather than a full claim-level scoring system
- there is no persistent report/version metadata store
- the generated report depends on the selected LLM provider and model
- the system does not attempt full regulatory PADER compliance

These limitations are intentional for a first working prototype.

---

## 22. Version 1 direction

A natural Version 1 would add:

1. Section-specific evidence requirements
2. Reusable analysis functions shared by multiple report types
3. Configurable prompts per report type and section
4. Report and prompt version tracking
5. Claim-to-evidence tracing
6. Automated evaluation of generated claims
7. Support for another report type such as PSUR or PBRER

The goal would be to extend the same core system rather than create a new generator for every report type.

---

## 23. Data usage

The supplied dataset and reference materials are provided solely for this hiring/technical evaluation exercise.

They are synthetic and/or derived from publicly available adverse-event reporting sources and do not represent confidential or real patient records.

The dataset and generated materials should not be redistributed or reused outside the scope of the assignment.

The local dataset copy should be deleted when the evaluation process is complete.
