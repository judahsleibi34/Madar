export const buildProfilePayload = (form) => ({
  first_name: form.first_name.trim(),
  last_name: form.last_name.trim(),
  phone: form.phone.trim(),
  avatar: form.avatar.trim(),
});
