# Dataset data dictionary

Source file: `backend/data/imports/india_scholarship_dataset_2026_27_researched.csv` (31 rows, 41 columns, UTF-8).
The data-quality findings from the Stage-1 audit are in [AUDIT_AND_PLAN.md](AUDIT_AND_PLAN.md#b-dataset-quality-report-india_scholarship_dataset_2026_27_researchedcsv).

## Column → structured field mapping (`app/services/normalize.py`, rules in `config/vocabulary.json`)

| CSV column(s) | Structured field(s) | Interpretation |
|---|---|---|
| `scholarship_id` | `external_id` | Required, unique per file |
| `scholarship_name` | `name`, `normalized_name` | Required |
| `provider`, `provider_type`, `scholarship_type` | same names | Type mapped to `government`/`private_foundation`/…, `merit`/`need`/`welfare`/`merit_cum_means` |
| `education_level` (+ `eligible_courses`, `year_of_study`) | `education_rule`, `education_levels`, `class_range`, `allowed_years` | Mapped via `education_level_map`; "Coaching" ⇒ `unknown`; class ranges only parsed from explicit "Class I-X" style text; years only from explicit "1st-4th year" style text |
| `eligible_fields` | `discipline_rule`, `disciplines` | `strict` (outside list fails), `open` ("and other …": outside list ⇒ question), `any`, `unknown` |
| `minimum_cgpa_or_percentage` + `minimum_marks_details` | `academic_rule`, `min_percentage`/`min_cgpa`, `academic_has_alternative`, `academic_note` | ≤10 ⇒ CGPA, ≤100 ⇒ percentage; "percentile" in details ⇒ question (not a percentage); "no fixed minimum" ⇒ `none`; otherwise `unknown`. " OR " in details ⇒ alternative route |
| `maximum_family_income` + `income_criteria_details` | `income_rule`, `income_limit`, `income_note` | Number ⇒ limit, **unless it contradicts an amount stated in the details text** (then `unknown` + CONFLICT note); "NO INCOME CEILING STATED" ⇒ `none` |
| `gender` | `genders` | `ANY` ⇒ no restriction |
| `category` | `categories`, `category_alt_tags`, `category_note` | "Government reservation norms" ⇒ no exclusive restriction (note kept); "PM CARES" ⇒ alternative beneficiary tag |
| `disability_requirement` | `disability_rule`, `min_disability_percent` | ">=40%" ⇒ required, 40 |
| `eligible_states`, `domicile_requirement` | `eligible_states`, `domicile_note` | "All India" ⇒ no restriction; names canonicalised |
| `special_background_requirement` | `conditions`, `special_note` | Split on `;`. Segments matching beneficiary tags are OR-ed into one `profile_tags` condition; citizenship phrases ⇒ `citizenship`; segments covered by another rule are dropped; everything else ⇒ per-scholarship **question** with a stable key |
| `scholarship_amount`, `amount_frequency` | `amount_text`, `amount_max_inr`, `amount_frequency` | Max amount only for display/sorting |
| `required_documents` | `required_documents` (list) | Split on `;`/`,` |
| `application_start_date`, `application_deadline` | `open_date`, `deadline` | ISO/DD-MM-YYYY/“5 Oct 2026”; impossible or ambiguous dates ⇒ null (never guessed) |
| `application_status` | `status_reported`, `renewal_type` | Stored as stated; availability is computed from dates, not from this text |
| `official_application_url`, `official_source_url` | `application_url`, `official_source_url` | Non-http(s) values rejected |
| `short_description`, `eligibility_summary`, `selection_process`, `combination_restrictions` | `description`, `eligibility_summary`, `selection_process`, `exclusions` | Free text |
| `source_last_verified` | evidence `retrieved_at` | Kept as the dataset's own claim (`verification_status = dataset_claim`); does not set `last_verified_at` |

Columns not mapped (kept only in the raw file): `income_period`, `eligible_regions`, `benefit_description`,
`source_name`, `verification_notes`, `can_combine_with_other_scholarships`, `exclusive_scholarship_rule`.

## Interpretation results on the bundled dataset

- 19/31 rows carry interpretation notes (see **Operations → Data quality → Dataset imports → Row-level report**).
- Detected inconsistencies: IND-NSP-009/010 income `2500000` vs "₹2.5 lakh" in the details text (stored as unknown,
  needs verification); IND-NSP-014 "80" is the 80th percentile (stored as a question).

## Importing a replacement dataset

Use the same column names (at least the required ones listed in `csv_import.REQUIRED_COLUMNS`). In
**Operations → Data quality → Dataset imports**, upload the CSV with a new version label:

- **Queue changes for review** (default): new rows are created; differences on existing rows become pending changes.
- **Apply changes**: differences are applied and recorded as accepted by you, with a new record version.

CLI equivalent: `python -m app.cli import --file new.csv --version 2027-28-v1 --mode review`.

## Student profile fields

Only attributes used by a rule are collected: education level, class/year, discipline, course name (free text,
not used for decisions), qualifying-exam percentage, CGPA + scale, annual family income, state, gender, category,
disability status/percentage, citizenship, special-circumstance tags. All are optional; null means unknown. No
identity numbers, documents or financial records are collected.
