export const PASSWORD_MIN_LENGTH = 8;

export const meetsMinimumPasswordPolicy = (password) =>
  String(password || "").length >= PASSWORD_MIN_LENGTH;
