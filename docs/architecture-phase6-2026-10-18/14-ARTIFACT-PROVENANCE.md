# Artifact categories and executed identity

For exact a8fac208586a331d79ce5d02cc5adf32410d57f3:

- Backend CI: https://github.com/judahsleibi34/Madar/actions/runs/39124278195
- Frontend CI: https://github.com/judahsleibi34/Madar/actions/runs/39124278224
- Fresh image CI: https://github.com/judahsleibi34/Madar/actions/runs/39124278251
- Artifact12135995156,authenticated ZIP digest
  a99534bdf67d199fccfcf2cac76d174c4465db7b524b1e7909a2ebd7b42a1a99.
- Backend/worker OCI runtime imageID:
  06cb727a1912e96abdf72b28e1abe782f7efd7b08f752763e14b9bc0a8c0130b.
- Frontend OCI runtime imageID:
  6156891f830d69092150942db439c7ea57b8188ff202771049ad590ea4f2d17b.

The existing fetch verifier authenticated repository,run,attempt,exact source,
artifact metadata/archive bytes,build receipt and OCI identities. Independent
backend/frontend check records were verified before staging mutation. Actual
containers used those imageIDs,exact source/build labels and expected runtime
code hashes; no /app source mounts. These are fresh locked CI images accepted in
synthetic staging,not installed-controller acceptance or production authorization.
A new source commit requires new exact-source images and application-CI evidence.
The historical schema148 artifact workflow name does not attest runtime schema.

Recovery tooling authenticates origin150 and target source images separately.
An old source backup can be used to validate a newer compatible target application;
it cannot be relabeled as a fresh image of the new source. Original source service
resumption continues to bind its own original source/image/container preimages.

## Frozen final code candidate

Exact36bb910fa028d380a0fb130bb8beeb1b0990bd2d fresh image workflow
[39128295629](https://github.com/judahsleibi34/Madar/actions/runs/39128295629)
PASS,artifact12136249264. Independently verified backend/frontend source checks
passed before staging use. Authenticated ZIP digest:
`sha256:ef9f635d47b285b6e44de41669f321b52645fac7f4ac2944dbd43cc521e3ecfd`.
Backend/worker OCI runtime identity:
`sha256:2dfe12742434d5aa8c8159273a8ab53a306d71b34a459eadbe6562e78d5e3ff0`.
Frontend OCI runtime identity:
`sha256:4619f66617518c5273fe04a726fbc853cefdb21e522416574ea8556946afa34c`.

Earlier8e17a128 full application restore used artifact12135754482/run39126113202,
ZIP`sha256:fad286cd5237654d3340d7d7d7a449dd86f572be9f082ac1e72d9c1e8104a651`,
backend`sha256:6da42a7eee965644bf320ea055415b995755b80c2ac7f08a2739507058bd1416`,
frontend`sha256:a149c259d53bba072bd545cc9e9bad92b253ec672ae66c02f73473c94a65d682`.
Each source has its own authenticated archives;none was relabeled. Documentation
commits after the frozen code candidate do not change its runtime source identity.
