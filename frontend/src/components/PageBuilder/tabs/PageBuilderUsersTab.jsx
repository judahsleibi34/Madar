import { useState } from "react";
import {
  RefreshCw,
  Settings,
  ShieldCheck,
  UserPlus,
  X,
} from "lucide-react";

const USER_STATUSES = ["Active", "Disabled"];

const getRoleForUser = (roles, user) =>
  roles.find((role) => role.id === user.roleId) ||
  (user.roleId
    ? {
        id: user.roleId,
        name: user.roleId === "customer" ? "Customer" : user.roleId,
        permissions: {},
      }
    : null);

const countEnabledPermissions = (role) =>
  Object.values(role?.permissions || {}).filter(Boolean).length;

export default function PageBuilderUsersTab({
  project,
  users,
  usersLoading,
  usersError,
  userMutationId,
  selected,
  selectedRole,
  permissionGroups,
  addUser,
  addRole,
  updateUser,
  updateRole,
  deleteUser,
  reloadUsers,
  setSelected,
}) {
  const siteUsers = Array.isArray(users) ? users : [];
  const roles = Array.isArray(project.roles) ? project.roles : [];
  const activeUsers = siteUsers.filter((user) => user.status === "Active").length;
  const disabledUsers = siteUsers.filter((user) => user.status === "Disabled").length;
  const editableRole = selectedRole || roles[0] || null;
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createError, setCreateError] = useState("");
  const [createBusy, setCreateBusy] = useState(false);
  const [newUser, setNewUser] = useState({
    fullName: "",
    email: "",
    password: "",
    roleId: roles[0]?.id || "customer",
    status: "Active",
  });
  const editableRolePermissions = countEnabledPermissions(editableRole);
  const totalPermissions = permissionGroups.reduce(
    (total, group) => total + group.permissions.length,
    0
  );
  const createRoleOptions = roles.some((role) => role.id === "customer")
    ? roles
    : [{ id: "customer", name: "Customer" }, ...roles];

  const openCreateUser = () => {
    setCreateError("");
    setNewUser({
      fullName: "",
      email: "",
      password: "",
      roleId: roles[0]?.id || "customer",
      status: "Active",
    });
    setIsCreateOpen(true);
  };

  const submitNewUser = async (event) => {
    event.preventDefault();
    setCreateBusy(true);
    setCreateError("");
    try {
      await addUser({
        full_name: newUser.fullName.trim(),
        email: newUser.email.trim(),
        password: newUser.password,
        role_id: newUser.roleId || "customer",
        status: newUser.status.toLowerCase(),
      });
      setIsCreateOpen(false);
    } catch (error) {
      setCreateError(error?.message || "Could not add this user.");
    } finally {
      setCreateBusy(false);
    }
  };

  return (
    <div className="workspace-page users-workspace-page">
      <div className="workspace-header users-workspace-header">
        <div>
          <span className="workspace-kicker">Access control</span>
          <h2>Users and roles</h2>
          <p>
            Manage everyone registered on this subdomain, including accounts
            created by an administrator, and control their site role and access.
          </p>
          <div className="users-inline-stats" aria-label="Users summary">
            <span>
              <strong>{siteUsers.length}</strong> users
            </span>
            <span>
              <strong>{activeUsers}</strong> active
            </span>
            <span>
              <strong>{disabledUsers}</strong> disabled
            </span>
            <span>
              <strong>{roles.length}</strong> roles
            </span>
            <span>
              <strong>{totalPermissions}</strong> permissions
            </span>
          </div>
        </div>

        <div className="header-actions users-header-actions">
          <button type="button" className="primary-action" onClick={openCreateUser}>
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
              <h3>Subdomain users</h3>
              <p>{siteUsers.length} registered and admin-created account{siteUsers.length === 1 ? "" : "s"}.</p>
            </div>
            <button
              type="button"
              className="users-refresh-button"
              onClick={reloadUsers}
              disabled={usersLoading}
            >
              <RefreshCw size={16} />
              Refresh
            </button>
          </div>

          {usersError && <div className="users-load-error" role="alert">{usersError}</div>}
          {usersLoading && <div className="users-loading-state">Loading subdomain users…</div>}

          <div className="user-list users-table">
            <div className="users-table-head" aria-hidden="true">
              <span>Member</span>
              <span>Role</span>
              <span>Status</span>
              <span>Settings</span>
            </div>
            {!usersLoading && siteUsers.length === 0 && (
              <div className="users-empty-state">
                No one has registered on this subdomain yet. Add a user here or share the site registration page.
              </div>
            )}
            {siteUsers.map((user) => {
              const role = getRoleForUser(roles, user);
              const roleOptions = role && !roles.some((item) => item.id === role.id)
                ? [role, ...roles]
                : roles;
              const isUserSettingsOpen = selected?.type === "user" && selected.id === user.id;
              const isBusy = String(userMutationId || "") === String(user.id);

              return (
                <div
                  className={`user-row users-table-row ${isUserSettingsOpen ? "is-open" : ""}`}
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
                        <em>{user.source === "admin" ? "Created by admin" : "Registered on site"}</em>
                      </div>
                    </div>

                    <div className="user-card-summary">
                      <span>{role?.name || "No role"}</span>
                      <span>{user.status || "Active"}</span>
                    </div>

                    <button
                      type="button"
                      className="user-settings-button"
                      aria-expanded={isUserSettingsOpen}
                      aria-label={`Open settings for ${user.name || user.email || "user"}`}
                      title="User settings"
                      onClick={() =>
                        setSelected(
                          isUserSettingsOpen
                            ? { type: "page", id: project.activePageId || null }
                            : { type: "user", id: user.id }
                        )
                      }
                    >
                      <Settings size={17} />
                    </button>
                  </div>

                  {isUserSettingsOpen && (
                    <div className="user-settings-panel">
                      <label>
                        <span>Role</span>
                        <select
                          value={user.roleId || role?.id || ""}
                          disabled={isBusy}
                          onChange={(event) =>
                            updateUser(user.id, { roleId: event.target.value })
                          }
                        >
                          {roleOptions.map((item) => (
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
                          disabled={isBusy}
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
                          disabled={isBusy}
                          title="Remove website access"
                          onClick={() => deleteUser(user.id)}
                        >
                          Remove access
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
          </div>

          <div className="role-picker-list">
            {roles.length === 0 && (
              <div className="roles-empty-state">
                Add a role to define permissions, then assign it to any subdomain user.
              </div>
            )}
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

      {isCreateOpen && (
        <div className="user-create-modal-backdrop" role="presentation">
          <section
            className="user-create-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="create-site-user-title"
          >
            <div className="user-create-modal-header">
              <div>
                <span className="workspace-kicker">Subdomain access</span>
                <h3 id="create-site-user-title">Add user</h3>
                <p>Create an account that can sign in to this published site.</p>
              </div>
              <button
                type="button"
                className="user-create-modal-close"
                aria-label="Close add user dialog"
                onClick={() => setIsCreateOpen(false)}
              >
                <X size={18} />
              </button>
            </div>

            <form className="user-create-form" onSubmit={submitNewUser}>
              <label>
                <span>Full name</span>
                <input
                  autoFocus
                  required
                  minLength={2}
                  maxLength={160}
                  value={newUser.fullName}
                  onChange={(event) =>
                    setNewUser((current) => ({ ...current, fullName: event.target.value }))
                  }
                />
              </label>

              <label>
                <span>Email</span>
                <input
                  type="email"
                  required
                  value={newUser.email}
                  onChange={(event) =>
                    setNewUser((current) => ({ ...current, email: event.target.value }))
                  }
                />
              </label>

              <label>
                <span>Temporary password</span>
                <input
                  type="password"
                  required
                  minLength={8}
                  maxLength={200}
                  autoComplete="new-password"
                  value={newUser.password}
                  onChange={(event) =>
                    setNewUser((current) => ({ ...current, password: event.target.value }))
                  }
                />
                <small>The user can sign in immediately with this password.</small>
              </label>

              <div className="user-create-form-grid">
                <label>
                  <span>Role</span>
                  <select
                    value={newUser.roleId}
                    onChange={(event) =>
                      setNewUser((current) => ({ ...current, roleId: event.target.value }))
                    }
                  >
                    {createRoleOptions.map((role) => (
                      <option key={role.id} value={role.id}>{role.name}</option>
                    ))}
                  </select>
                </label>

                <label>
                  <span>Status</span>
                  <select
                    value={newUser.status}
                    onChange={(event) =>
                      setNewUser((current) => ({ ...current, status: event.target.value }))
                    }
                  >
                    {USER_STATUSES.map((status) => (
                      <option key={status} value={status}>{status}</option>
                    ))}
                  </select>
                </label>
              </div>

              {createError && <div className="user-create-error" role="alert">{createError}</div>}

              <div className="user-create-actions">
                <button type="button" onClick={() => setIsCreateOpen(false)} disabled={createBusy}>
                  Cancel
                </button>
                <button type="submit" className="primary-action" disabled={createBusy}>
                  <UserPlus size={17} />
                  {createBusy ? "Adding…" : "Create user"}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
