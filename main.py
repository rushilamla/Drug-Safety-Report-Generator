import json
import os
from pathlib import Path

import pandas as pd
from google import genai


# --------------------------------------------------
# Configuration
# --------------------------------------------------

DATA_PATH = "data/Bisoprolol_icsr_sample_1068rows.xlsx"

REPORT_CONFIG = {
    "report_type": "PADER",
    "product": "Bisoprolol",
    "required_sections": [
        "Reporting Period",
        "Narrative Summary and Analysis",
        "Summary Analysis of Cases",
        "Reaction / Adverse Event Analysis",
        "Serious Cases / 15-Day Alerts",
        "Trends and Important Observations",
        "History of Safety-Related Actions",
        "Limitations"
    ]
}


# --------------------------------------------------
# Data loading
# --------------------------------------------------

def load_data():
    return pd.read_excel(DATA_PATH)


# --------------------------------------------------
# Age processing
# --------------------------------------------------

def normalize_age(df):

    df["age_years"] = pd.NA

    df.loc[
        df["patient_patientonsetageunit"] == "year",
        "age_years"
    ] = df["patient_patientonsetage"]

    df.loc[
        df["patient_patientonsetageunit"] == "month",
        "age_years"
    ] = df["patient_patientonsetage"] / 12

    df.loc[
        df["patient_patientonsetageunit"] == "week",
        "age_years"
    ] = df["patient_patientonsetage"] / 52

    df.loc[
        df["patient_patientonsetageunit"] == "day",
        "age_years"
    ] = df["patient_patientonsetage"] / 365

    # 800 is an unknown/invalid age unit in this dataset.
    df.loc[
        df["patient_patientonsetageunit"].astype(str) == "800",
        "age_years"
    ] = pd.NA

    df["age_years"] = pd.to_numeric(
        df["age_years"],
        errors="coerce"
    )

    bins = [
        -float("inf"),
        18,
        45,
        65,
        75,
        float("inf")
    ]

    labels = [
        "<18",
        "18–44",
        "45–64",
        "65–74",
        "75+"
    ]

    df["age_group"] = pd.cut(
        df["age_years"],
        bins=bins,
        labels=labels,
        right=False
    )

    df["age_group"] = (
        df["age_group"]
        .astype("object")
        .fillna("Unknown")
    )

    return df


# --------------------------------------------------
# Helper for comma-separated reaction/outcome fields
# --------------------------------------------------

def split_values(value):

    if pd.isna(value):
        return []

    return [
        item.strip()
        for item in str(value).split(",")
        if item.strip()
    ]


# --------------------------------------------------
# Build reaction-level data
# --------------------------------------------------

def build_reaction_data(df):

    reaction_rows = []
    mismatch_count = 0

    for _, row in df.iterrows():

        reactions = split_values(
            row["patient_reaction_reactionmeddrapt"]
        )

        outcomes = split_values(
            row["patient_reaction_reactionoutcome"]
        )

        # We cannot safely match outcomes to reactions
        # when their counts are different.
        if len(reactions) != len(outcomes):

            mismatch_count += 1

            for reaction in reactions:

                reaction_rows.append({
                    "safetyreportid":
                        row["safetyreportid"],

                    "reaction":
                        reaction,

                    "outcome":
                        "Unavailable",

                    "outcome_reliable":
                        False,

                    "serious":
                        row["serious"],

                    "age_group":
                        row["age_group"],

                    "sex":
                        row["patient_patientsex"],

                    "country":
                        row["occurcountry"],

                    "report_date":
                        row["report_date"],

                    "reporter_qualification":
                        row["primarysource_qualification"]
                })

            continue

        # Normal case: every reaction has a matching outcome.
        for reaction, outcome in zip(
            reactions,
            outcomes
        ):

            reaction_rows.append({
                "safetyreportid":
                    row["safetyreportid"],

                "reaction":
                    reaction,

                "outcome":
                    outcome,

                "outcome_reliable":
                    True,

                "serious":
                    row["serious"],

                "age_group":
                    row["age_group"],

                "sex":
                    row["patient_patientsex"],

                "country":
                    row["occurcountry"],

                "report_date":
                    row["report_date"],

                "reporter_qualification":
                    row["primarysource_qualification"]
            })

    reaction_df = pd.DataFrame(
        reaction_rows
    )

    reaction_df.attrs[
        "outcome_mismatch_rows"
    ] = mismatch_count

    return reaction_df


# --------------------------------------------------
# Deterministic analysis
# --------------------------------------------------

def run_analysis(df, reaction_df):

    # One row per unique case for case-level analysis.
    case_df = (
        df
        .drop_duplicates("safetyreportid")
        .copy()
    )

    total_cases = (
        case_df["safetyreportid"]
        .nunique()
    )

    serious_cases = (
        case_df["serious"] == "serious"
    ).sum()

    non_serious_cases = (
        case_df["serious"] == "not serious"
    ).sum()

    # Monthly case counts.
    monthly_cases = (
        case_df
        .assign(
            month=(
                case_df["report_date"]
                .dt
                .to_period("M")
                .astype(str)
            )
        )
        .groupby("month")["safetyreportid"]
        .nunique()
    )

    # 15-day / expedited cases.
    alert_cases = case_df[
        case_df[
            "fulfillexpeditecriteria"
        ]
        .astype(str)
        .str.lower()
        .eq("yes")
    ].copy()

    # The challenge's deterministic example uses
    # the source reaction field for this analysis.
    top_reactions = (
        df[
            "patient_reaction_reactionmeddrapt"
        ]
        .dropna()
        .value_counts()
        .head(15)
        .to_dict()
    )

    top_serious_reactions = (
        df[
            df["serious"] == "serious"
        ][
            "patient_reaction_reactionmeddrapt"
        ]
        .dropna()
        .value_counts()
        .head(15)
        .to_dict()
    )

    # Only use reaction/outcome pairs where the
    # source contained the same number of values.
    reliable_reactions = reaction_df[
        reaction_df["outcome_reliable"]
    ]

    outcomes = (
        reliable_reactions["outcome"]
        .value_counts()
        .to_dict()
    )

    mismatch_rows = int(
        reaction_df.attrs.get(
            "outcome_mismatch_rows",
            0
        )
    )

    results = {

        "reporting_period": {
            "start": str(
                case_df["report_date"]
                .min()
                .date()
            ),
            "end": str(
                case_df["report_date"]
                .max()
                .date()
            )
        },

        "total_cases":
            int(total_cases),

        "serious_cases":
            int(serious_cases),

        "non_serious_cases":
            int(non_serious_cases),

        "age_groups": (
            case_df["age_group"]
            .value_counts()
            .to_dict()
        ),

        "sex": (
            case_df["patient_patientsex"]
            .fillna("Unknown")
            .value_counts()
            .to_dict()
        ),

        "country": (
            case_df["occurcountry"]
            .fillna("Unknown")
            .value_counts()
            .to_dict()
        ),

        "reporter_qualification": (
            case_df[
                "primarysource_qualification"
            ]
            .fillna("Unknown")
            .value_counts()
            .to_dict()
        ),

        "top_reactions":
            top_reactions,

        "top_serious_reactions":
            top_serious_reactions,

        "outcomes":
            outcomes,

        "monthly_cases":
            monthly_cases.to_dict(),

        "alert_analysis": {

            "alert_cases":
                int(
                    alert_cases[
                        "safetyreportid"
                    ].nunique()
                ),

            "alert_serious_cases":
                int(
                    (
                        alert_cases["serious"]
                        == "serious"
                    ).sum()
                ),

            "alert_non_serious_cases":
                int(
                    (
                        alert_cases["serious"]
                        == "not serious"
                    ).sum()
                )
        },

        "data_quality": {

            "reaction_outcome_mismatch_rows":
                mismatch_rows
        }
    }

    return results


# --------------------------------------------------
# Generate narrative with the LLM
# --------------------------------------------------

def generate_report(
    analysis_results,
    report_config
):

    project_root = (
        Path(__file__)
        .resolve()
        .parent
        .parent
    )

    prompt_path = (
        project_root
        / "prompts"
        / "report_prompt.txt"
    )

    report_path = (
        project_root
        / "report_output.md"
    )

    # Read the prompt template.
    with open(
        prompt_path,
        "r",
        encoding="utf-8"
    ) as f:

        prompt_template = f.read()

    # Convert Python dictionaries to readable JSON
    # before giving them to the model.
    report_configuration = json.dumps(
        report_config,
        indent=2,
        ensure_ascii=False
    )

    evidence_packet = json.dumps(
        analysis_results,
        indent=2,
        ensure_ascii=False
    )

    # Insert configuration and evidence into prompt.
    prompt = prompt_template.replace(
        "{{REPORT_CONFIG}}",
        report_configuration
    )

    prompt = prompt.replace(
        "{{EVIDENCE_PACKET}}",
        evidence_packet
    )

    # Read Gemini API key from environment.
    api_key = os.environ.get(
        "GEMINI_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set."
        )

    client = genai.Client(
        api_key=api_key
    )

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt
    )

    report = response.text

    # Save the LLM-generated part.
    with open(
        report_path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(report)

    return report


# --------------------------------------------------
# Build case index
# --------------------------------------------------

def build_case_index(
    reaction_df
):

    case_index = reaction_df[
        [
            "safetyreportid",
            "reaction",
            "serious",
            "report_date",
            "country",
            "outcome"
        ]
    ].copy()

    case_index = case_index.rename(
        columns={
            "safetyreportid":
                "Case ID",

            "reaction":
                "Reaction",

            "serious":
                "Seriousness",

            "report_date":
                "Reporting Date",

            "country":
                "Country",

            "outcome":
                "Outcome"
        }
    )

    case_index[
        "Reporting Date"
    ] = (
        pd.to_datetime(
            case_index["Reporting Date"]
        )
        .dt
        .strftime("%Y-%m-%d")
    )

    return case_index


# --------------------------------------------------
# Add human review + case index
# --------------------------------------------------

def append_submission_sections(
    report,
    reaction_df
):

    case_index = build_case_index(
        reaction_df
    )

    case_index_markdown = (
        case_index
        .to_markdown(index=False)
    )

    human_review = """
## Human Review

**Status:** Pending human review

The generated report should be reviewed against the deterministic analysis results before being treated as final.
"""

    return (
        report.strip()
        + "\n\n"
        + human_review
        + "\n\n"
        + "## 8. Case Index / Listing\n\n"
        + case_index_markdown
    )


# --------------------------------------------------
# Main program
# --------------------------------------------------

def main():

    print("Loading dataset...")
    df = load_data()

    print("Normalizing age...")
    df = normalize_age(df)

    print("Building reaction-level data...")
    reaction_df = build_reaction_data(df)

    print("Running deterministic analysis...")
    results = run_analysis(
        df,
        reaction_df
    )

    print(
        "\nDeterministic analysis complete."
    )

    print(
        json.dumps(
            results,
            indent=2,
            ensure_ascii=False
        )
    )

    print(
        "\nGenerating report with LLM..."
    )

    report = generate_report(
        results,
        REPORT_CONFIG
    )

    final_report = (
        append_submission_sections(
            report,
            reaction_df
        )
    )

    project_root = (
        Path(__file__)
        .resolve()
        .parent
        .parent
    )

    report_path = (
        project_root
        / "report_output.md"
    )

    with open(
        report_path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(final_report)

    print(
        "\nReport generated successfully."
    )

    print(
        f"Saved to: {report_path}"
    )


if __name__ == "__main__":
    main()