import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  CreditCard,
  RefreshCw,
  Search,
  ShieldCheck,
  UserCog,
  UsersRound,
} from "lucide-react";

const API_URL = import.meta.env.VITE_API_URL || "/api";
const USER_PAGE_CACHE_MS = 30_000;
const USER_PAGE_SIZE = 10;
const USER_PAGE_SIZE_OPTIONS = [10, 20, 50];

const labels = {
  kicker: "Admin",
  title: "User Management",
  subtitle: "Review accounts, roles, tenant plans, and payment status from one workspace.",
  search: "Search users",
  refresh: "Refresh",
  totalUsers: "Total users",
  admins: "Admins",
  activePlans: "Active plans",
  page: "Page",
  previous: "Previous",
  next: "Next",
  shownUsers: "Shown users",
  usersPerPage: "Users per page",
  role: "Role",
  plan: "Plan",
  status: "Status",
  builder: "Builder",
  tenant: "Tenant",
  user: "User",
  admin: "Admin",
  saveRole: "Save role",
  applyPlan: "Apply plan",
  noUsers: "No users found.",
  loading: "Loading users",
  forbidden: "Only admins can manage users.",
  loadError: "Could not load users.",
  saved: "Changes saved.",
  fullPlatform: "Full platform",
  individualBuilder: "Individual builder",
};

const platformPlans = ["starter", "pro", "business"];
const builderPlans = ["basic", "premium"];
const builderTypes = ["website", "forms", "quiz", "reservation", "reports", "data"];
const paymentStatuses = ["pending", "active", "past_due", "canceled"];

const friendlyLabels = {
  subscription_type: {
    full_platform: "Full platform",
    individual_builder: "Single builder",
  },
  plan: {
    starter: "Starter",
    pro: "Pro",
    business: "Business",
    basic: "Basic",
    premium: "Premium",
  },
  builder_type: {
    website: "Website",
    forms: "Forms",
    quiz: "Quiz",
    reservation: "Reservation",
    reports: "Reports",
    data: "Data analysis",
  },
  payment_status: {
    pending: "Pending setup",
    active: "Active",
    past_due: "Payment issue",
    canceled: "Canceled",
  },
};

function friendlyValue(group, value) {
  return friendlyLabels[group]?.[value] || value || "None";
}

function getDisplayName(user) {
  const name = `${user.first_name || ""} ${user.last_name || ""}`.trim();
  return name || user.email || "Madar User";
}

function getPrimaryFeature(user) {
  return user.features?.[0] || {
    subscription_type: user.subscription_type || "individual_builder",
    plan: user.subscription_type === "full_platform" ? "starter" : "basic",
    builder_type: user.subscription_type === "full_platform" ? null : "website",
    payment_status: user.payment_status || "pending",
  };
}

function UserRow({ user, onRoleSave, onPlanSave, busyKey }) {
  const feature = getPrimaryFeature(user);
  const [role, setRole] = useState(user.user_type || "user");
  const [planForm, setPlanForm] = useState({
    subscription_type: feature.subscription_type || "individual_builder",
    plan: feature.plan || "basic",
    builder_type: feature.builder_type || "website",
    payment_status: feature.payment_status || "pending",
  });

  useEffect(() => {
    setRole(user.user_type || "user");
    setPlanForm({
      subscription_type: feature.subscription_type || "individual_builder",
      plan: feature.plan || "basic",
      builder_type: feature.builder_type || "website",
      payment_status: feature.payment_status || "pending",
    });
  }, [
    user.id,
    user.user_type,
    feature.subscription_type,
    feature.plan,
    feature.builder_type,
    feature.payment_status,
  ]);

  const isPlatform = planForm.subscription_type === "full_platform";
  const planOptions = isPlatform ? platformPlans : builderPlans;
  const roleBusy = busyKey === `role-${user.id}`;
  const planBusy = busyKey === `plan-${user.id}`;

  const updatePlanField = (field, value) => {
    setPlanForm((prev) => {
      const next = { ...prev, [field]: value };

      if (field === "subscription_type") {
        const nextIsPlatform = value === "full_platform";
        next.plan = nextIsPlatform ? "starter" : "basic";
        next.builder_type = nextIsPlatform ? null : "website";
      }

      return next;
    });
  };

  return (
    <article className="user-management-row">
      <div className="user-management-profile">
        <div className="user-management-avatar">
          {getDisplayName(user).slice(0, 1).toUpperCase()}
        </div>
        <div>
          <h3>{getDisplayName(user)}</h3>
          <p>{user.email}</p>
          <span>
            {labels.tenant}: {user.tenant_id || "none"}
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

      <div className="user-management-plan-grid">
        <label>
          <span>{labels.plan}</span>
          <select
            value={planForm.subscription_type}
            onChange={(event) => updatePlanField("subscription_type", event.target.value)}
          >
            <option value="full_platform">{labels.fullPlatform}</option>
            <option value="individual_builder">
              {friendlyValue("subscription_type", "individual_builder")}
            </option>
          </select>
        </label>

        <label>
          <span>{labels.plan}</span>
          <select
            value={planForm.plan}
            onChange={(event) => updatePlanField("plan", event.target.value)}
          >
            {planOptions.map((plan) => (
              <option key={plan} value={plan}>
                {friendlyValue("plan", plan)}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>{labels.builder}</span>
          <select
            value={planForm.builder_type || ""}
            onChange={(event) => updatePlanField("builder_type", event.target.value)}
            disabled={isPlatform}
          >
            {isPlatform ? (
              <option value="">none</option>
            ) : (
              builderTypes.map((type) => (
                <option key={type} value={type}>
                  {friendlyValue("builder_type", type)}
                </option>
              ))
            )}
          </select>
        </label>

        <label>
          <span>{labels.status}</span>
          <select
            value={planForm.payment_status}
            onChange={(event) => updatePlanField("payment_status", event.target.value)}
          >
            {paymentStatuses.map((status) => (
              <option key={status} value={status}>
                {friendlyValue("payment_status", status)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <button
        type="button"
        className="user-management-primary"
        onClick={() => onPlanSave(user, planForm)}
        disabled={planBusy || !user.tenant_id}
      >
        {planBusy ? <RefreshCw size={16} /> : <CreditCard size={16} />}
        {labels.applyPlan}
      </button>
    </article>
  );
}

export default function UserManagementPage({ currentUser }) {
  const [users, setUsers] = useState([]);
  const [searchInput, setSearchInput] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(USER_PAGE_SIZE);
  const [pagination, setPagination] = useState({
    page: 1,
    page_size: pageSize,
    has_next_page: false,
    has_previous_page: false,
  });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busyKey, setBusyKey] = useState("");
  const userPageCacheRef = useRef(new Map());

  const isAdmin = currentUser?.user_type === "admin";

  const loadUsers = async ({ silent = false, force = false } = {}) => {
    if (!isAdmin) {
      setLoading(false);
      setRefreshing(false);
      setError(labels.forbidden);
      return;
    }

    if (silent && users.length) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    setError("");

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

      const response = await fetch(`${API_URL}/admin/users?${params.toString()}`, {
        credentials: "include",
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
      setError(loadError.message || labels.loadError);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPage(1);
      setSearchTerm(searchInput.trim());
    }, 350);

    return () => window.clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    loadUsers({ silent: users.length > 0 });
  }, [isAdmin, page, pageSize, searchTerm]);

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
      total: users.length,
      admins: adminCount,
      active: activeCount,
    };
  }, [users]);

  const saveRole = async (userId, userType) => {
    setBusyKey(`role-${userId}`);
    setError("");
    setMessage("");

    try {
      const response = await fetch(`${API_URL}/admin/users/${userId}/user-type`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_type: userType }),
      });

      if (!response.ok) {
        throw new Error(labels.loadError);
      }

      userPageCacheRef.current.clear();
      await loadUsers({ silent: true, force: true });
      setMessage(labels.saved);
    } catch (saveError) {
      setError(saveError.message || labels.loadError);
    } finally {
      setBusyKey("");
    }
  };

  const savePlan = async (user, planForm) => {
    setBusyKey(`plan-${user.id}`);
    setError("");
    setMessage("");

    try {
      const response = await fetch(`${API_URL}/admin/billing/features`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tenant_id: user.tenant_id,
          subscription_type: planForm.subscription_type,
          plan: planForm.plan,
          builder_type:
            planForm.subscription_type === "full_platform"
              ? null
              : planForm.builder_type,
          payment_status: planForm.payment_status,
        }),
      });

      if (!response.ok) {
        throw new Error(labels.loadError);
      }

      userPageCacheRef.current.clear();
      await loadUsers({ silent: true, force: true });
      setMessage(labels.saved);
    } catch (saveError) {
      setError(saveError.message || labels.loadError);
    } finally {
      setBusyKey("");
    }
  };

  return (
    <section className="user-management-page">
      <header className="admin-dashboard-header user-management-header">
        <div>
          <span className="user-management-kicker">{labels.kicker}</span>
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

      {message && (
        <div className="user-management-notice success">
          <CheckCircle2 size={17} />
          {message}
        </div>
      )}

      {error && (
        <div className="user-management-notice error">
          <AlertCircle size={17} />
          {error}
        </div>
      )}

      <div className="user-management-list">
        {loading ? (
          <div className="dashboard-panel user-management-empty">
            <RefreshCw size={20} />
            {labels.loading}
          </div>
        ) : users.length ? (
          users.map((user) => (
            <UserRow
              key={user.id}
              user={user}
              onRoleSave={saveRole}
              onPlanSave={savePlan}
              busyKey={busyKey}
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
