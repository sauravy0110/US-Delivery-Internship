# Evaluation Report

Generated: 2026-08-27T13:18:25Z  
Duration: 56.97s

## Task 1 — Ticket Triage

**6/6 passed** (0 skipped, avg quality score: 0.993)

| Case | Passed | Quality Score | Description |
|---|---|---|---|
| `triage_01_clear_p1_outage` | ✅ | 0.993 | Clear-cut critical outage should classify as P1 Bug/Integration with urgent draft response |
| `triage_02_billing_question` | ✅ | 0.993 | Routine billing question should NOT be classified urgent |
| `triage_03_how_to_request` | ✅ | 0.993 | How-to / documentation request, low urgency, should route to Tier-1 |
| `triage_04_feature_request` | ✅ | 0.993 | Feature request should be categorised correctly and routed to Product Management, not urgent |
| `triage_05_data_loss_urgent` | ✅ | 0.993 | Explicit data loss language should trigger high urgency and Data Loss category |
| `triage_06_adversarial_ambiguous` | ✅ | 0.994 | ADVERSARIAL: vague, low-context ticket with no clear product/category signal. Should still degrade gracefully to a valid enum value rather than crashing or returning an invalid category. |

<details><summary>Detailed checks</summary>

**triage_01_clear_p1_outage**
- ✅ urgency_tier is a valid enum value — `P1`
- ✅ issue_category is a valid enum value — `Bug`
- ✅ urgency_tier in ['P1'] — `P1`
- ✅ issue_category in ['Bug', 'Integration', 'Performance'] — `Bug`
- ✅ has at least one KB match — `3`
- ✅ draft_first_response is non-empty/substantive — `499`
- ✅ LLM-as-judge: draft response quality >= 0.5 — `{'professional': True, 'on_topic': True, 'score': 0.95, 'notes': 'Professional and on‑topic; acknowledges the outage and error without adding any unfounded details.'}`

**triage_02_billing_question**
- ✅ urgency_tier is a valid enum value — `P4`
- ✅ issue_category is a valid enum value — `Billing`
- ✅ urgency_tier in ['P3', 'P4'] — `P4`
- ✅ issue_category in ['Billing'] — `Billing`
- ✅ has at least one KB match — `3`
- ✅ draft_first_response is non-empty/substantive — `316`
- ✅ LLM-as-judge: draft response quality >= 0.5 — `{'professional': True, 'on_topic': True, 'score': 0.95, 'notes': 'Professional and directly addresses the request without adding unsupported details.'}`

**triage_03_how_to_request**
- ✅ urgency_tier is a valid enum value — `P4`
- ✅ issue_category is a valid enum value — `How-To`
- ✅ urgency_tier in ['P3', 'P4'] — `P4`
- ✅ issue_category in ['How-To'] — `How-To`
- ✅ has at least one KB match — `3`
- ✅ draft_first_response is non-empty/substantive — `427`
- ✅ LLM-as-judge: draft response quality >= 0.5 — `{'professional': True, 'on_topic': True, 'score': 0.95, 'notes': 'Professional and directly addresses the request with appropriate documentation link, no fabricated information.'}`

**triage_04_feature_request**
- ✅ urgency_tier is a valid enum value — `P4`
- ✅ issue_category is a valid enum value — `Feature Request`
- ✅ urgency_tier in ['P3', 'P4'] — `P4`
- ✅ issue_category in ['Feature Request'] — `Feature Request`
- ✅ draft_first_response is non-empty/substantive — `490`
- ✅ LLM-as-judge: draft response quality >= 0.5 — `{'professional': True, 'on_topic': True, 'score': 0.96, 'notes': 'Professional and on‑topic; acknowledges the bulk‑approval request without adding any unsupported facts.'}`

**triage_05_data_loss_urgent**
- ✅ urgency_tier is a valid enum value — `P1`
- ✅ issue_category is a valid enum value — `Data Loss`
- ✅ urgency_tier in ['P1', 'P2'] — `P1`
- ✅ issue_category in ['Data Loss'] — `Data Loss`
- ✅ has at least one KB match — `3`
- ✅ draft_first_response is non-empty/substantive — `605`
- ✅ LLM-as-judge: draft response quality >= 0.5 — `{'professional': True, 'on_topic': True, 'score': 0.95, 'notes': 'The response is polite, addresses the missing Finance files after CloudSync backup, and does not introduce any unsupported facts.'}`

**triage_06_adversarial_ambiguous**
- ✅ urgency_tier is a valid enum value — `P3`
- ✅ issue_category is a valid enum value — `Bug`
- ✅ urgency_tier in ['P1', 'P2', 'P3', 'P4'] — `P3`
- ✅ issue_category in ['Bug', 'Feature Request', 'How-To', 'Performance', 'Billing', 'Integration', 'Onboarding', 'Data Loss'] — `Bug`
- ✅ draft_first_response is non-empty/substantive — `377`
- ✅ LLM-as-judge: draft response quality >= 0.5 — `{'professional': True, 'on_topic': True, 'score': 0.96, 'notes': 'Professional, on‑topic, and contains no fabricated details.'}`
- ✅ execution did not raise an exception — `ok`

</details>

## Task 2 — Account Brief

**6/6 passed** (0 skipped, avg quality score: 1.0)

| Case | Passed | Quality Score | Description |
|---|---|---|---|
| `account_01_valid_account_basic` | ✅ | 1.0 | Any valid account with tickets should produce a non-empty, well-formed brief |
| `account_02_churning_account_flags_risk` | ✅ | 1.0 | An account with health_status='Churning' or negative escalation_notes should surface at least one quote-justified risk flag |
| `account_03_healthy_account_low_noise` | ✅ | 1.0 | A Healthy account with no negative escalation notes should not have fabricated risk flags |
| `account_04_determinism` | ✅ | 1.0 | Calling the same account_id twice must return a byte-identical brief (determinism requirement) |
| `account_05_no_recent_tickets` | ✅ | 1.0 | An account with zero tickets in the last 90 days should still produce a brief, not error out |
| `account_06_adversarial_unknown_id` | ✅ | 1.0 | ADVERSARIAL: account_id with no matching record (documented data gap) must be handled gracefully, not raise an exception |

<details><summary>Detailed checks</summary>

**account_01_valid_account_basic**
- ✅ found == True — `True`
- ✅ executive_summary is non-empty/substantive — `Omni Consumer Products is a $500K ARR account marked At Risk with inactive usage`
- ✅ >= 1 talking points — `5`

**account_02_churning_account_flags_risk**
- ✅ found == True — `True`
- ✅ >= 1 risk flags — `3`
- ✅ risk-flag quotes are verbatim from source data — `3 flag(s) checked`

**account_03_healthy_account_low_noise**
- ✅ found == True — `True`
- ✅ executive_summary is non-empty/substantive — `Polaris Group is a healthy APAC energy customer with $120,000 ARR and an increas`

**account_04_determinism**
- ✅ found == True — `True`
- ✅ repeat call returns identical output — `match`

**account_05_no_recent_tickets**
- ✅ found == True — `True`
- ✅ executive_summary is non-empty/substantive — `Omni Consumer Products is a $500K ARR account marked At Risk with inactive usage`

**account_06_adversarial_unknown_id**
- ✅ found == False — `False`
- ✅ error field populated for missing account — `No account found with account_id='ACC-DOES-NOT-EXIST-99999'. Ticket/account_id references without a matching account are a known, documented data gap — handled gracefully rather than raising.`
- ✅ execution did not raise an exception — `ok`

</details>
