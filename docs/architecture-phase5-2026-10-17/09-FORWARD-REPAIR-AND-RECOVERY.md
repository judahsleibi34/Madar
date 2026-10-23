# Recovery rules

Never restart protocol1 delivery workers after147 or unfenced outbox resolvers
after149. Neither committed migration is a down-migration operation. Intermediate
147/148 remain READ_ONLY; partial execution needs independently authorized forward
repair and a fresh executor scope. No consumed approval or historical receipt is
reused. A lost response is not proof of rollback or provider failure.

Provider intent/preimages persist privately before effects. Uncertain interrupted
effects require actual observation, fresh authority and reconciliation, not blind
retry. Explicit staging recovery proves original roles and provider functionality
without fabricating missing production boot/replica/write authority. Production
controller integration remains unavailable and rejects before effects.
