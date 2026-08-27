-- Retire the legacy Gemini AI-provider pricing metadata.
--
-- Migration 071 remains immutable because it records the historical schema
-- transition that originally introduced this catalog row. Madar no longer
-- supports Gemini at runtime, so the historical multiplier must not remain
-- eligible for new token-metering decisions.

update public.ai_token_model_multipliers
set active = false
where lower(provider) = 'gemini'
  and active is distinct from false;
