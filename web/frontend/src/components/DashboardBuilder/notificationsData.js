const notificationSeeds = [
  {
    id: "new-response",
    contentKey: "newResponse",
    groupKey: "today",
    sourceKey: "forms",
    unread: true,
  },
  {
    id: "site-published",
    contentKey: "sitePublished",
    groupKey: "today",
    sourceKey: "builder",
    unread: true,
  },
  {
    id: "workspace-health",
    contentKey: "workspaceHealth",
    groupKey: "today",
    sourceKey: "system",
    unread: false,
  },
  {
    id: "plan-reminder",
    contentKey: "planReminder",
    groupKey: "yesterday",
    sourceKey: "billing",
    unread: false,
  },
  {
    id: "data-import",
    contentKey: "dataImport",
    groupKey: "yesterday",
    sourceKey: "data",
    unread: false,
  },
];

export function getDummyNotifications(t) {
  return notificationSeeds.map((item) => ({
    ...item,
    title: t(`notifications.dummy.${item.contentKey}.title`),
    detail: t(`notifications.dummy.${item.contentKey}.detail`),
    time: t(`notifications.dummy.${item.contentKey}.time`),
    group: t(`notifications.groups.${item.groupKey}`),
    source: t(`notifications.sourcesList.${item.sourceKey}`),
  }));
}
