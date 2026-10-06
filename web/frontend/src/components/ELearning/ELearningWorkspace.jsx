import { Navigate, Route, Routes, useParams } from "react-router-dom";
import ELearningTerminologyProvider from "./ELearningTerminologyProvider";
import AcademyLandingPageEntry from "./AcademyLandingPageEntry";
import AcademyManagementHub from "./AcademyManagementHub";
import ELearningSettingsPage from "../DashboardBuilder/ELearningSettingsPage";
import ELearningCoursesPage from "./ELearningCoursesPage";
import ELearningCoursePage from "./ELearningCoursePage";
import ELearningDirectoryPage from "./ELearningDirectoryPage";
import ELearningRelationshipsPage from "./ELearningRelationshipsPage";
import ELearningLessonPage from "./ELearningLessonPage";
import ELearningPlansPage from "./ELearningPlansPage";
import "../../styles/admin/dashboard/elearning-management.css";

function CourseRoute() {
  const { courseId } = useParams();
  return <ELearningCoursePage key={courseId} />;
}

function LessonRoute() {
  const { courseId, lessonId } = useParams();
  return <ELearningLessonPage key={`${courseId}:${lessonId}`} />;
}

export default function ELearningWorkspace({ user }) {
  return <ELearningTerminologyProvider key={`${user?.tenant_id}:${user?.id}`}>
    <Routes>
      <Route index element={<Navigate to="courses" replace />} />
      <Route path="courses" element={<ELearningCoursesPage />} />
      <Route path="courses/:courseId" element={<CourseRoute />} />
      <Route path="courses/:courseId/:tab" element={<CourseRoute />} />
      <Route path="courses/:courseId/lessons/:lessonId" element={<LessonRoute />} />
      <Route path="groups/:itemId/:tab?" element={<ELearningRelationshipsPage kind="group" />} />
      <Route path="instructors/:itemId/:tab?" element={<ELearningRelationshipsPage kind="instructor" />} />
      <Route path="groups" element={<ELearningDirectoryPage key="groups" kind="groups" />} />
      <Route path="instructors" element={<ELearningDirectoryPage key="instructors" kind="instructors" />} />
      <Route path="settings" element={<ELearningSettingsPage user={user} />} />
      <Route path="landing-page" element={<AcademyLandingPageEntry key={`${user?.tenant_id}:${user?.id}`} />} />
      <Route path="academy-access" element={<AcademyManagementHub user={user} />} />
      <Route path="settings/academy" element={<Navigate to="/e-learning/academy-access" replace />} />
      <Route path="plans" element={<ELearningPlansPage />} />
      <Route path="settings/plans" element={<Navigate to="/e-learning/plans" replace />} />
      <Route path="*" element={<Navigate to="/e-learning/courses" replace />} />
    </Routes>
  </ELearningTerminologyProvider>;
}
