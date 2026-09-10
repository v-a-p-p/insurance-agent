# Eval Sample Conversations

Source: `/namastex-fde-challenge/dataset/conversations.parquet`

## Selection Criteria

10 conversations hand-picked to maximize outcome and feature diversity:

- **Outcomes**: ganho (2), perdido (2), em_negociacao (3), sem_resposta (3)
- **Opening styles**: greeting-only (5), direct-quote (5)
- **Objection categories**: price_complaint, competitor_mention, preciso_pensar, ghosting, age_refusal, vehicle_refusal
- **Plan tiers**: premium (3), completo (4), essencial (2)
- **Age ranges**: 18-24, 25-34, 35-59, 76+
- **CEP risk**: high-risk prefixes (07/08/21/26/59), low-risk
- **Vehicle years**: 0-5, 6-10, 11-20

Only `sender_role == "lead"` messages are replayed into the agent. Vendor messages are preserved for reference and manual inspection.

The dataset is synthetic — conversations follow common templates. All PII (CPF, email, phone) is synthetically generated and not real.