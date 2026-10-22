# Application identity: data-key generation, unwrap, and rewrap only.
# Key creation, rotation, deletion, policy changes, audit administration, and token
# administration belong to a separate operator identity.
path "transit/datakey/plaintext/madar-data-sources" {
  capabilities = ["update"]
}

path "transit/decrypt/madar-data-sources" {
  capabilities = ["update"]
}

path "transit/rewrap/madar-data-sources" {
  capabilities = ["update"]
}

path "auth/token/lookup-self" {
  capabilities = ["read"]
}

path "auth/token/renew-self" {
  capabilities = ["update"]
}
