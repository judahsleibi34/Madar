import { permissionGroups } from "./PageBuilder.constants";
import { createRole, createUser } from "./PageBuilder.factories";

export default function PageBuilderUsers({
  project,
  updateProject,
  selectedRole,
  setSelected,
  showToast,
}) {
  const addRole = () => {
    const role = createRole(`Role ${project.roles.length + 1}`);

    updateProject((prev) => ({
      ...prev,
      roles: [...prev.roles, role],
      activeRoleId: role.id,
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
                ...role.permissions,
                ...(updates.permissions || {}),
              },
            }
          : role
      ),
    }));
  };

  const addUser = () => {
    const user = createUser(
      `User ${project.users.length + 1}`,
      `user${project.users.length + 1}@madar.local`,
      project.roles[0]?.id || ""
    );

    updateProject((prev) => ({
      ...prev,
      users: [...prev.users, user],
    }));

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

    if (user.isCurrentUser) {
      alert("You cannot delete the currently logged-in user.");
      return;
    }

    if (!window.confirm(`Delete user "${user.name}"?`)) return;

    updateProject((prev) => ({
      ...prev,
      users: prev.users.filter((item) => item.id !== userId),
    }));

    showToast("User deleted.");
  };

  return (
    <div className="workspace-page">
      <div className="workspace-header">
        <div>
          <h2>Users & Roles</h2>
          <p>Manage team members, roles, and permissions.</p>
        </div>

        <div className="header-actions">
          <button type="button" onClick={addUser}>
            + User
          </button>
          <button type="button" onClick={addRole}>
            + Role
          </button>
        </div>
      </div>

      <div className="users-grid">
        <section className="dashboard-panel">
          <h3>Team Members</h3>

          <div className="user-list">
            {project.users.map((user) => {
              const isCurrentUser = Boolean(user.isCurrentUser);

              return (
                <div className="user-row" key={user.id}>
                  <div className="user-row-main">
                    <strong>{user.name}</strong>
                    <span>{user.email}</span>
                  </div>

                  <select
                    value={user.roleId}
                    onChange={(event) =>
                      updateUser(user.id, { roleId: event.target.value })
                    }
                  >
                    {project.roles.map((role) => (
                      <option key={role.id} value={role.id}>
                        {role.name}
                      </option>
                    ))}
                  </select>

                  <select
                    value={user.status}
                    onChange={(event) =>
                      updateUser(user.id, { status: event.target.value })
                    }
                  >
                    <option>Active</option>
                    <option>Invited</option>
                    <option>Disabled</option>
                  </select>

                  <button
                    type="button"
                    className="danger-lite user-delete-button"
                    disabled={isCurrentUser}
                    title={
                      isCurrentUser
                        ? "The account owner cannot delete himself"
                        : "Delete user"
                    }
                    onClick={() => deleteUser(user.id)}
                  >
                    {isCurrentUser ? "Owner" : "Delete"}
                  </button>
                </div>
              );
            })}
          </div>
        </section>

        <section className="dashboard-panel">
          <h3>Roles</h3>

          <div className="roles-list">
            {project.roles.map((role) => (
              <div
                className={`role-card ${
                  selectedRole?.id === role.id ? "active" : ""
                }`}
                key={role.id}
                onClick={() => setSelected({ type: "role", id: role.id })}
              >
                <input
                  value={role.name}
                  onChange={(event) =>
                    updateRole(role.id, { name: event.target.value })
                  }
                />

                <textarea
                  value={role.description}
                  placeholder="Role description"
                  onChange={(event) =>
                    updateRole(role.id, { description: event.target.value })
                  }
                />

                {permissionGroups.map((group) => (
                  <div className="permission-group" key={group.title}>
                    <strong>{group.title}</strong>

                    {group.permissions.map((permission) => (
                      <label className="checkbox-control" key={permission.key}>
                        <input
                          type="checkbox"
                          checked={Boolean(role.permissions[permission.key])}
                          onChange={(event) =>
                            updateRole(role.id, {
                              permissions: {
                                [permission.key]: event.target.checked,
                              },
                            })
                          }
                        />
                        {permission.label}
                      </label>
                    ))}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}