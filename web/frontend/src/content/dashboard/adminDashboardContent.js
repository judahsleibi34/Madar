export const adminDashboardContent = {
  en: { title: "Dashboard", runningProjects: "Running Projects", users: "Users", totalRevenue: "Total Revenue", uptime: "Uptime" },
  ar: { title: "لوحة التحكم", runningProjects: "المشاريع النشطة", users: "المستخدمون", totalRevenue: "إجمالي الإيرادات", uptime: "وقت التشغيل" },
};

export const getAdminDashboardContent = (lang = "en") =>
  adminDashboardContent[lang === "ar" ? "ar" : "en"];
