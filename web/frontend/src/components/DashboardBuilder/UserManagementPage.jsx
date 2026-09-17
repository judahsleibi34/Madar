import { Link } from "react-router-dom";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  Search,
  ShieldCheck,
  Trash2,
  UserCog,
  UsersRound,
} from "lucide-react";
import PageDeleteConfirmModal from "../PageBuilder/modals/PageDeleteConfirmModal";
import LoadingBar from "../common/LoadingBar";
import { apiFetch } from "../../utils/apiClient";
import {
  getUserManagementLabels,
} from "../../content";

const API_URL = import.meta.env.VITE_API_URL || "/api";
const USER_PAGE_CACHE_MS = 30_000;
const USER_PAGE_SIZE = 10;
const USER_PAGE_SIZE_OPTIONS = [10, 20, 50];

const deferEffectStateUpdate = (callback) => {
  let cancelled = false;
  queueMicrotask(() => {
    if (!cancelled) callback();
  });
  return () => {
    cancelled = true;
  };
};

function getDisplayName(user, labels = getUserManagementLabels("en")) {
  const name = `${user.first_name || ""} ${user.last_name || ""}`.trim();
  return name || user.email || labels.fallbackUser;
}

function UserRow({
  user,
  onRoleSave,
  onRequestDelete,
  busyKey,
  labels,
}) {
  const [role, setRole] = useState(user.user_type || "user");
  useEffect(() => deferEffectStateUpdate(() => setRole(user.user_type || "user")), [user.id, user.user_type]);

  const roleBusy = busyKey === `role-${user.id}`;
  const deleteBusy = busyKey === `delete-${user.id}`;

  return (
    <article className="user-management-row">
      <div className="user-management-half user-management-identity-half">
        <div className="user-management-profile">
          <div className="user-management-avatar">
            {getDisplayName(user, labels).slice(0, 1).toUpperCase()}
          </div>
          <div>
            <h3>{getDisplayName(user, labels)}</h3>
            <p>{user.email}</p>
            <span>
              {labels.tenant}: {user.tenant_id || labels.none}
            </span>
          </div>
        </div>

        <div className="user-management-controls">
          <label>
            <span>{labels.role}</span>
            <select value={role} onChange={(event) => setRole(event.target.value)}>
              <option value="user">{labels.user}</option>
              <option value="admin">{labels.admin}</option>
            </select>
          </label>

          <button
            type="button"
            className="user-management-secondary"
            onClick={() => onRoleSave(user.id, role)}
            disabled={roleBusy || role === (user.user_type || "user")}
          >
            {roleBusy ? <RefreshCw size={16} /> : <ShieldCheck size={16} />}
            {labels.saveRole}
          </button>
        </div>
      </div>

      <div className="user-management-half user-management-management-half">
        <div className="user-management-actions">
          {user.tenant_id && <Link className="user-management-primary" to={`/admin/commercial/${user.tenant_id}`}>Commercial access</Link>}

            <button
              type="button"
              className="user-management-danger"
              onClick={() => onRequestDelete(user)}
              disabled={roleBusy || deleteBusy}
            >
              {deleteBusy ? <RefreshCw size={16} /> : <Trash2 size={16} />}
              {labels.deleteUser}
            </button>
        </div>
      </div>
    </article>
  );
}

function UserManagementSkeleton({ labels }) {
  return (
    <div className="user-management-loading-bar">
      <LoadingBar mode="inline" label={labels.loading} />
    </div>
  );
}

export default function UserManagementPage({ currentUser, lang = "en" }) {
  const activeLang = lang === "ar" ? "ar" : "en";
  const labels = getUserManagementLabels(activeLang);
  const [users, setUsers] = useState([]);
  const [searchInput, setSearchInput] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(USER_PAGE_SIZE);
  const [pagination, setPagination] = useState({
    page: 1,
    page_size: pageSize,
    total_count: 0,
    has_next_page: false,
    has_previous_page: false,
  });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [toast, setToast] = useState(null);
  const [busyKey, setBusyKey] = useState("");
  const [deleteTargetUser, setDeleteTargetUser] = useState(null);
  const userPageCacheRef = useRef(new Map());

  const isAdmin = currentUser?.user_type === "admin";

  const showToast = useCallback((type, text) => {
    setToast({
      id: Date.now(),
      type,
      text,
    });
  }, []);

  useEffect(() => {
    if (!toast) return undefined;

    const timeoutId = window.setTimeout(() => {
      setToast((currentToast) => (
        currentToast?.id === toast.id ? null : currentToast
      ));
    }, 3200);

    return () => window.clearTimeout(timeoutId);
  }, [toast]);

  const loadUsers = useCallback(async ({ silent = false, force = false } = {}) => {
    if (!isAdmin) {
      setLoading(false);
      setRefreshing(false);
      showToast("error", labels.forbidden);
      return;
    }

    if (silent) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    try {
      const cacheKey = `${page}:${pageSize}:${searchTerm}`;
      const cachedPage = userPageCacheRef.current.get(cacheKey);
      const cacheIsFresh =
        cachedPage && Date.now() - cachedPage.loadedAt < USER_PAGE_CACHE_MS;

      if (!force && cacheIsFresh) {
        setUsers(cachedPage.users);
        setPagination(cachedPage.pagination);
        setLoading(false);
        setRefreshing(false);
        return;
      }

      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
      });

      if (searchTerm) {
        params.set("search", searchTerm);
      }

      const response = await apiFetch(`${API_URL}/admin/users?${params.toString()}`, {
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error(labels.loadError);
      }

      const data = await response.json();
      const nextUsers = data.users || [];
      const nextPagination = data.pagination || {
        page,
        page_size: pageSize,
        total_count: nextUsers.length,
        has_next_page: false,
        has_previous_page: page > 1,
      };

      userPageCacheRef.current.set(cacheKey, {
        users: nextUsers,
        pagination: nextPagination,
        loadedAt: Date.now(),
      });

      setUsers(nextUsers);
      setPagination(nextPagination);
    } catch (loadError) {
      showToast("error", loadError.message || labels.loadError);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [isAdmin, labels.forbidden, labels.loadError, page, pageSize, searchTerm, showToast]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPage(1);
      setSearchTerm(searchInput.trim());
    }, 350);

    return () => window.clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    return deferEffectStateUpdate(() => {
      loadUsers({ silent: users.length > 0 });
    });
  }, [loadUsers, users.length]);

  const changePageSize = (nextPageSize) => {
    setPage(1);
    setPageSize(nextPageSize);
  };

  const stats = useMemo(() => {
    const adminCount = users.filter((user) => user.user_type === "admin").length;
    const activeCount = users.filter((user) =>
      (user.features || []).some((feature) => feature.payment_status === "active")
    ).length;

    return {
      total: pagination.total_count ?? users.length,
      admins: adminCount,
      active: activeCount,
    };
  }, [pagination.total_count, users]);

  const saveRole = async (userId, userType) => {
    setBusyKey(`role-${userId}`);

    try {
      const response = await apiFetch(`${API_URL}/admin/users/${userId}/user-type`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_type: userType }),
      });

      if (!response.ok) {
        throw new Error(labels.loadError);
      }

      userPageCacheRef.current.clear();
      await loadUsers({ silent: true, force: true });
      showToast("success", labels.saved);
    } catch (saveError) {
      showToast("error", saveError.message || labels.loadError);
    } finally {
      setBusyKey("");
    }
  };

  const deleteUser = async (user) => {
    if (!user?.id) {
      showToast("error", labels.loadError);
      return;
    }

    setBusyKey(`delete-${user.id}`);

    try {
      const response = await apiFetch(`${API_URL}/admin/users/${user.id}`, {
        method: "DELETE",
      });

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.detail || labels.loadError);
      }

      userPageCacheRef.current.clear();
      setDeleteTargetUser(null);
      await loadUsers({ silent: true, force: true });
      showToast("success", labels.deleted);
    } catch (deleteError) {
      showToast("error", deleteError.message || labels.loadError);
    } finally {
      setBusyKey("");
    }
  };

  return (
    <section className="user-management-page">
      <header className="admin-dashboard-header user-management-header app-page-intro">
        <div>
          <h1>{labels.title}</h1>
          <p>{labels.subtitle}</p>
        </div>
        <button
          type="button"
          onClick={() => loadUsers({ silent: true, force: true })}
          className="user-management-secondary"
          disabled={refreshing}
        >
          <RefreshCw size={16} className={refreshing ? "is-spinning" : ""} />
          {labels.refresh}
        </button>
      </header>

      <div className="user-management-stats">
        <article>
          <UsersRound size={18} />
          <span>{labels.shownUsers}</span>
          <strong>{stats.total}</strong>
        </article>
        <article>
          <ShieldCheck size={18} />
          <span>{labels.admins}</span>
          <strong>{stats.admins}</strong>
        </article>
        <article>
          <CheckCircle2 size={18} />
          <span>{labels.activePlans}</span>
          <strong>{stats.active}</strong>
        </article>
      </div>

      <div className="user-management-toolbar">
        <Search size={18} />
        <input
          value={searchInput}
          onChange={(event) => setSearchInput(event.target.value)}
          placeholder={labels.search}
        />
      </div>

      {deleteTargetUser && (
        <PageDeleteConfirmModal
          page={{ name: getDisplayName(deleteTargetUser, labels) }}
          title={labels.deleteTitle}
          message={
            <>
              <strong>{getDisplayName(deleteTargetUser, labels)}</strong>
              <br />
              {labels.deleteMessage}
            </>
          }
          cancelLabel={labels.cancelDelete}
          confirmLabel={
            busyKey === `delete-${deleteTargetUser.id}`
              ? labels.deletingUser
              : labels.confirmDelete
          }
          confirmDisabled={busyKey === `delete-${deleteTargetUser.id}`}
          onCancel={() => setDeleteTargetUser(null)}
          onConfirm={() => deleteUser(deleteTargetUser)}
        />
      )}

      {toast && (
        <div className="user-management-toast-wrap" role="status" aria-live="polite">
          <div className={`user-management-toast ${toast.type}`}>
            {toast.type === "error" ? <AlertCircle size={17} /> : <CheckCircle2 size={17} />}
            <span>{toast.text}</span>
          </div>
        </div>
      )}

      <div className="user-management-list">
        {loading ? (
          <UserManagementSkeleton labels={labels} />
        ) : users.length ? (
          users.map((user) => (
            <UserRow
              key={user.id}
              user={user}
              onRoleSave={saveRole}
              onRequestDelete={setDeleteTargetUser}
              busyKey={busyKey}
              labels={labels}
            />
          ))
        ) : (
          <div className="dashboard-panel user-management-empty">
            <UserCog size={20} />
            {labels.noUsers}
          </div>
        )}
      </div>

      {!loading && users.length > 0 && (
        <div className="user-management-pagination">
          <label>
            <span>{labels.usersPerPage}</span>
            <select
              value={pageSize}
              onChange={(event) => changePageSize(Number(event.target.value))}
              disabled={refreshing}
            >
              {USER_PAGE_SIZE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>

          <button
            type="button"
            className="user-management-secondary"
            onClick={() => setPage((currentPage) => Math.max(currentPage - 1, 1))}
            disabled={!pagination.has_previous_page || refreshing}
          >
            {labels.previous}
          </button>

          <span>
            {labels.page} {pagination.page || page}
          </span>

          <button
            type="button"
            className="user-management-secondary"
            onClick={() => setPage((currentPage) => currentPage + 1)}
            disabled={!pagination.has_next_page || refreshing}
          >
            {labels.next}
          </button>
        </div>
      )}
    </section>
  );
}
