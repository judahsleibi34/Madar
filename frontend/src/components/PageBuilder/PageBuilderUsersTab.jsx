export default function PageBuilderUsersTab({
  project,
  selectedRole,
  permissionGroups,
  addUser,
  addRole,
  updateUser,
  updateRole,
  deleteUser,
  setSelected,
}) {
  return (
    <div className="workspace-page">
      <div className="workspace-header">
        <div>
          <h2>Users & Roles</h2>
          <p>Front-end-only mock users and permissions. Backend auth comes later.</p>
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
              const isMainAdmin = user.email === "admin@madar.local";

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
                    disabled={isMainAdmin}
                    title={isMainAdmin ? "Main admin cannot be deleted" : "Delete user"}
                    onClick={() => deleteUser(user.id)}
                  >
                    Delete
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
                className={`role-card ${selectedRole?.id === role.id ? "active" : ""}`}
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