import {
  KeyRound,
  Settings,
  ShieldCheck,
  UserPlus,
  UsersRound,
} from "lucide-react";

const USER_STATUSES = ["Active", "Invited", "Disabled"];

const getRoleForUser = (roles, user) =>
  roles.find((role) => role.id === user.roleId) || roles[0] || null;

const countEnabledPermissions = (role) =>
  Object.values(role?.permissions || {}).filter(Boolean).length;

export default function PageBuilderUsersTab({
  project,
  selected,
  selectedRole,
  permissionGroups,
  addUser,
  addRole,
  updateUser,
  updateRole,
  deleteUser,
  setSelected,
}) {
  const users = Array.isArray(project.users) ? project.users : [];
  const roles = Array.isArray(project.roles) ? project.roles : [];
  const activeUsers = users.filter((user) => user.status === "Active").length;
  const invitedUsers = users.filter((user) => user.status === "Invited").length;
  const editableRole = selectedRole || roles[0] || null;
  const editableRolePermissions = countEnabledPermissions(editableRole);
  const totalPermissions = permissionGroups.reduce(
    (total, group) => total + group.permissions.length,
    0
  );

  return (
    <div className="workspace-page users-workspace-page">
      <div className="workspace-header users-workspace-header">
        <div>
          <span className="workspace-kicker">Access control</span>
          <h2>Users and roles</h2>
          <p>
            Manage who can edit this builder project, what role they have, and
            which parts of the workspace each role can access.
          </p>
          <div className="users-inline-stats" aria-label="Users summary">
            <span>
              <strong>{users.length}</strong> users
            </span>
            <span>
              <strong>{activeUsers}</strong> active
            </span>
            <span>
              <strong>{roles.length}</strong> roles
            </span>
            <span>
              <strong>{totalPermissions}</strong> permissions
            </span>
          </div>
        </div>

        <div className="header-actions">
          <button type="button" onClick={addUser}>
            <UserPlus size={17} />
            Add user
          </button>
          <button type="button" onClick={addRole}>
            <ShieldCheck size={17} />
            Add role
          </button>
        </div>
      </div>

      <div className="users-grid users-management-grid">
        <section className="dashboard-panel users-panel">
          <div className="users-panel-heading">
            <div>
              <span className="workspace-kicker">Team</span>
              <h3>Team members</h3>
              <p>{invitedUsers} invited member{invitedUsers === 1 ? "" : "s"} waiting.</p>
            </div>
            <UsersRound size={22} />
          </div>

          <div className="user-list users-table">
            {users.map((user) => {
              const role = getRoleForUser(roles, user);
              const isProtected = Boolean(user.isCurrentUser) || user.email === "admin@madar.local";
              const isUserSettingsOpen = selected?.type === "user" && selected.id === user.id;

              return (
                <div
                  className={`user-row users-table-row ${isProtected ? "is-protected" : ""} ${isUserSettingsOpen ? "is-open" : ""}`}
                  key={user.id}
                >
                  <div className="user-card-header">
                    <div className="user-row-main">
                      <span className="user-avatar" aria-hidden="true">
                        {(user.name || user.email || "U").slice(0, 1).toUpperCase()}
                      </span>
                      <div>
                        <strong>{user.name}</strong>
                        <span>{user.email || "No email set"}</span>
                        {isProtected && <em>Owner account</em>}
                      </div>
                    </div>

                    <button
                      type="button"
                      className="user-settings-button"
                      aria-expanded={isUserSettingsOpen}
                      aria-label={`Open settings for ${user.name || user.email || "user"}`}
                      title="User settings"
                      onClick={() => setSelected({ type: "user", id: user.id })}
                    >
                      <Settings size={17} />
                    </button>
                  </div>

                  <div className="user-card-summary">
                    <span>{role?.name || "No role"}</span>
                    <span>{user.status || "Active"}</span>
                  </div>

                  {isUserSettingsOpen && (
                    <div className="user-settings-panel">
                      <label>
                        <span>Role</span>
                        <select
                          value={user.roleId || role?.id || ""}
                          onChange={(event) =>
                            updateUser(user.id, { roleId: event.target.value })
                          }
                        >
                          {roles.map((item) => (
                            <option key={item.id} value={item.id}>
                              {item.name}
                            </option>
                          ))}
                        </select>
                      </label>

                      <label>
                        <span>Status</span>
                        <select
                          value={user.status || "Active"}
                          onChange={(event) =>
                            updateUser(user.id, { status: event.target.value })
                          }
                        >
                          {USER_STATUSES.map((status) => (
                            <option key={status} value={status}>
                              {status}
                            </option>
                          ))}
                        </select>
                      </label>

                      <div className="user-card-actions">
                        <button
                          type="button"
                          className="danger-lite user-delete-button"
                          disabled={isProtected}
                          title={
                            isProtected
                              ? "The owner account stays in this project"
                              : "Delete user"
                          }
                          onClick={() => deleteUser(user.id)}
                        >
                          {isProtected ? "Owner" : "Delete"}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>

        <aside className="dashboard-panel users-roles-panel">
          <div className="users-panel-heading">
            <div>
              <span className="workspace-kicker">Roles</span>
              <h3>Role permissions</h3>
              <p>{editableRolePermissions} of {totalPermissions} permissions enabled.</p>
            </div>
            <KeyRound size={22} />
          </div>

          <div className="role-picker-list">
            {roles.map((role) => (
              <button
                type="button"
                className={editableRole?.id === role.id ? "active" : ""}
                key={role.id}
                onClick={() => setSelected({ type: "role", id: role.id })}
              >
                <strong>{role.name}</strong>
                <span>
                  {countEnabledPermissions(role)} / {totalPermissions} permissions
                </span>
              </button>
            ))}
          </div>

          {editableRole && (
            <div className="role-editor-card">
              <div className="role-editor-summary">
                <div>
                  <span>Editing role</span>
                  <strong>{editableRole.name}</strong>
                </div>
                <em>{editableRolePermissions}/{totalPermissions}</em>
              </div>

              <div className="role-editor-fields-grid">
                <label className="role-editor-field">
                  <span>Role name</span>
                  <input
                    value={editableRole.name}
                    onChange={(event) =>
                      updateRole(editableRole.id, { name: event.target.value })
                    }
                  />
                </label>

                <label className="role-editor-field">
                  <span>Description</span>
                  <input
                    value={editableRole.description || ""}
                    placeholder="Short role note"
                    onChange={(event) =>
                      updateRole(editableRole.id, { description: event.target.value })
                    }
                  />
                </label>
              </div>

              <div className="permissions-matrix">
                {permissionGroups.map((group) => (
                  <section className="permission-group" key={group.title}>
                    <strong>{group.title}</strong>

                    {group.permissions.map((permission) => (
                      <label className="checkbox-control" key={permission.key}>
                        <input
                          type="checkbox"
                          checked={Boolean(editableRole.permissions?.[permission.key])}
                          onChange={(event) =>
                            updateRole(editableRole.id, {
                              permissions: {
                                [permission.key]: event.target.checked,
                              },
                            })
                          }
                        />
                        {permission.label}
                      </label>
                    ))}
                  </section>
                ))}
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
