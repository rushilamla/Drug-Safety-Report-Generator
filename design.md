# Version 1 Design — Reusable Regulatory Reporting System

## Goal

Version 0 proves that raw ICSR data can be transformed into a grounded,
human-reviewable PADER-style report.

Version 1 would make the system reusable across different report types
without rewriting the core analysis pipeline.

---

## 1. Core idea

Keep the following components shared across report types:

```text
Data ingestion
      ↓
Data validation
      ↓
Reusable deterministic analyses
      ↓
Evidence layer
      ↓
Report-specific configuration
      ↓
LLM generation
      ↓
Human review
```

PADER, PSUR, PBRER, DSUR, and CSR would use the same core system but
different report configurations.

---

## 2. Report configuration

Instead of hard-coding the report type, each report type would define
configuration such as:

```text
report_type
required_sections
required_analyses
required_evidence
generation_instructions
validation_rules
```

Example:

```text
PADER
 ├── case summary
 ├── reaction analysis
 ├── 15-day alerts
 └── case listing

PSUR
 ├── signal analysis
 ├── benefit-risk information
 └── regulatory actions
```

The underlying data-processing code would remain shared where possible.

---

## 3. Section-specific evidence

Each report section would declare the evidence it needs.

For example:

```text
Narrative Summary
    → case counts
    → demographics
    → outcomes

Reaction Analysis
    → reaction counts
    → serious reaction counts

15-Day Alert Analysis
    → alert cases
    → seriousness
    → outcomes
    → case IDs
```

This avoids sending unnecessary information to the LLM.

It also makes the evidence flow easier to trace.

---

## 4. Reusable analyses

Common analyses would be implemented once and reused by multiple report
types.

Examples:

```text
unique case count
serious case count
reaction frequencies
outcome distribution
demographic breakdown
time trends
geographic distribution
```

A new report type should use these existing analyses whenever they satisfy
its requirements instead of implementing the same logic again.

---

## 5. Grounding and traceability

The evidence layer would retain links between generated claims and the
deterministic analyses that produced the supporting values.

A future report could therefore provide:

```text
Generated claim
      ↓
Evidence item
      ↓
Analysis
      ↓
Source cases
```

This would make review easier and improve trust in generated reports.

---

## 6. Evaluation

Version 1 would add automated checks such as:

- required sections are present
- numerical claims match deterministic evidence
- case counts are consistent
- unsupported claims are flagged
- report-specific requirements are satisfied

A set of fixed test datasets could be used to evaluate the system across
many generated reports instead of checking only one output manually.

---

## 7. Versioning

Each generated report could record:

```text
dataset version
analysis version
report configuration version
prompt version
model
generation timestamp
```

This would make it possible to reproduce or investigate a previous report.

---

## 8. Expected result

The final architecture would become:

```text
                    Reporting Task
                          ↓
                Report Configuration
                          ↓
                  Evidence Planning
                          ↓
                Reusable Analyses
                          ↓
                    Evidence Layer
                          ↓
                 LLM Report Generation
                          ↓
                    Validation
                          ↓
                    Human Review
                          ↓
                  Final Report
```

The objective is not to create a separate generator for every regulatory
report type.

The objective is to build a small reporting system in which different
reporting tasks can be expressed mainly through configuration and data,
while the core evidence and analysis capabilities remain reusable.
