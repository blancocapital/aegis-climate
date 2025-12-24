# Underwriter Tutorial

This guide walks through a practical underwriting workflow using the Workbench, Rules, and Referrals features.

## 1) Select a submission
1. Open **Underwriting → Submission Workbench**.
2. Choose an **Exposure Version**.
3. Check the readiness badge (READY / NEEDS REVIEW / NOT READY).

## 2) Improve readiness (if needed)
- If readiness is **NOT READY**, review validation errors and resolve missing TIV/location data.
- If readiness is **NEEDS REVIEW**, prioritize geocoding and data quality improvements.

Recommended actions:
- **Run geocode** to improve location quality.
- **Run rollup** to see concentrations and controls.
- **Run UW eval** after rules are configured.

## 3) Configure appetite & referral rules
1. Open **Underwriting → Appetite & Referral Rules**.
2. Create a rule using the safe predicate builder.
3. Verify the JSON preview matches your intent.

Example:
- If `hazard_band in ["HIGH","EXTREME"]` AND `tiv >= 1000000` → disposition **REFER**

## 4) Evaluate findings
1. In **Submission Workbench**, click **Run UW eval**.
2. Review **Referrals & conditions** for triggered findings.
3. Open **Underwriting → Referrals** to filter by status, severity, or location.

Actions:
- **ACK** to acknowledge a finding.
- **RESOLVE** to close it when addressed.
- Add a **note** for audit traceability.

## 5) Record a decision
1. In **Submission Workbench**, open the **Decision** card.
2. Select: **PROCEED**, **REFER**, **PROCEED_WITH_CONDITIONS**, or **DECLINE**.
3. Provide conditions (if any) and rationale.

## 6) Audit and governance
- All actions create audit events:
  - `uw_rule_created`
  - `uw_eval_requested`
  - `uw_finding_updated`
  - `note_created`
  - `decision_recorded`
- Review audit events in **Governance → Audit Log**.

---

### Tips
- Use **Referrals** to triage and add discipline before decisioning.
- Use **Notes** to document exceptions and coverage constraints.
- Keep rules minimal and deterministic for governance and repeatability.
