export const confirmIncompleteConnectionRemoval = () =>
  window.confirm("Remove this incomplete calendar connection?");

export const confirmConnectedAccountDisconnect = () =>
  window.confirm("Disconnect this account? Future synchronization will stop, but existing calendar events will remain.");
