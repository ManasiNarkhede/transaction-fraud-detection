/** Tooltip copy for Submit Transaction form fields. */
export const SUBMIT_TRANSACTION_FIELD_HELP = {
  user_id:
    'Your account ID — transactions you submit are scored under your account and only visible to you.',
  amount: 'Transaction amount in the selected currency. Used for amount-based rules and ML features.',
  currency: 'Three-letter ISO currency code (e.g. USD, EUR). Required for every submission.',
  merchant_id: 'Optional merchant identifier. Helps link repeat activity at the same merchant.',
  merchant_category:
    'Optional category (retail, travel, gambling, etc.). High-risk categories can trigger stricter rules.',
  location: 'Country or region code for the transaction (e.g. US, GB). Used for geo-anomaly checks.',
  payment_method: 'How the customer paid: card, wallet, transfer, crypto, or BNPL.',
  device_id: 'Device fingerprint or ID. New or untrusted devices increase risk scores.',
  ip_address: 'Client IP address at transaction time. Useful for location mismatch rules.',
  card_last_four: 'Last four digits of the card, if applicable. Must be exactly 4 digits.',
} as const;

/** Tooltip copy for New / Edit Rule form fields. */
export const RULE_FORM_FIELD_HELP = {
  name: 'Short, unique name shown in the rules table and when a rule triggers.',
  description: 'Optional longer explanation for analysts reviewing rule logic.',
  rule_type:
    'Category label for grouping (e.g. threshold, velocity, location). Does not change evaluation logic.',
  conditions:
    'When all (AND) or any (OR) of these checks match a transaction, the rule fires and applies its action/score.',
  action:
    'Block stops the transaction immediately when matched. Verify sends it to the OTP queue. Approve whitelists matching transactions — if an approve rule runs first (lower priority number), block rules below it never run.',
  priority:
    'Lower numbers run first. Put block rules at priority 1. If an approve rule with priority 1 matches the same transaction, it wins and block rules are skipped.',
  score_value:
    'Extra risk points when the rule triggers. Block and verify actions also add enough points to reach the correct score band automatically.',
} as const;
