export const ACADEMY_COMPONENT_TYPES = new Set([
  "heading", "text", "button", "image", "imageButton", "imageCardButton", "card",
  "carousel", "logoSlider", "list", "divider", "thinDivider", "metric",
  "academyFeaturedCourses", "academyCourseCollection", "academyPlans", "academyContinueLearning", "academyInstructors",
]);
export const ACADEMY_DATA_COMPONENT_TYPES = new Set([...ACADEMY_COMPONENT_TYPES].filter(type => type.startsWith("academy")));

// Presentation destinations only; authentication and access remain platform-owned.
export const getAcademyNavigationDestinations = base => [
  { label: "Courses", href: `${base}/courses` },
  { label: "Plans", href: `${base}/plans` },
  { label: "Sign In", href: `${base}/login` },
  { label: "My Learning", href: "/my-learning", requiresAuth: true },
];
