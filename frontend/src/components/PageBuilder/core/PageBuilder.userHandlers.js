export const createUserHandlers = ({
  project,
  updateProject,
  setSelected,
  showToast,
  createRole,
  createUser,
}) => {
  const addUser = () => {
    const user = createUser();

    updateProject((prev) => ({
      ...prev,
      users: [...prev.users, user],
      activeUserId: user.id,
    }));

    setSelected({ type: "user", id: user.id });
    showToast("User added.");
  };

  const updateUser = (userId, updates) => {
    updateProject((prev) => ({
      ...prev,
      users: prev.users.map((user) =>
        user.id === userId ? { ...user, ...updates } : user
      ),
    }));
  };

  const deleteUser = (userId) => {
    const user = project.users.find((item) => item.id === userId);

    if (!user) return;

    const isMainAdmin = user.email === "admin@madar.local";

    if (isMainAdmin) {
      alert("You cannot delete the main admin user.");
      return;
    }

    if (!window.confirm(`Delete user "${user.name}"?`)) return;

    updateProject((prev) => ({
      ...prev,
      users: prev.users.filter((item) => item.id !== userId),
    }));

    showToast("User deleted.");
  };

  const addRole = () => {
    const role = createRole(`Role ${project.roles.length + 1}`);

    updateProject((prev) => ({
      ...prev,
      roles: [...prev.roles, role],
    }));

    setSelected({ type: "role", id: role.id });
  };

  const updateRole = (roleId, updates) => {
    updateProject((prev) => ({
      ...prev,
      roles: prev.roles.map((role) =>
        role.id === roleId
          ? {
              ...role,
              ...updates,
              permissions: {
                ...(role.permissions || {}),
                ...(updates.permissions || {}),
              },
            }
          : role
      ),
    }));
  };

  return {
    addUser,
    updateUser,
    deleteUser,
    addRole,
    updateRole,
  };
};
