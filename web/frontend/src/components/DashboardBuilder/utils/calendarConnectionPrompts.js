export const confirmIncompleteConnectionRemoval = () =>
  window.confirm("Remove this incomplete calendar connection?");

export const confirmConnectedAccountDisconnect = () =>
  window.confirm("Disconnect this account? Future synchronization will stop, but existing calendar events will remain.");

export const confirmGoogleWriteUpgrade = () =>
  window.confirm(
    "Enable Google write access? Madar will be able to create, update, and—only when you explicitly choose it—delete synchronized Google events. Existing events will not be deleted automatically."
  );

export const chooseTaskDeletionMode = (isSynchronized) => {
  if (!isSynchronized) {
    return window.confirm("Delete this task from Madar?") ? "local_only" : null;
  }
  if (
    window.confirm(
      "Delete this task from both Madar and Google Calendar? Choose Cancel to keep the Google event."
    )
  ) {
    return "local_and_provider";
  }
  return window.confirm("Delete only the Madar task and keep the Google event?")
    ? "local_only"
    : null;
};
