import { getResponsesContent } from '../../content/pageBuilder/responsesContent';

// Presentation vocabulary only. Builder's data hooks and submission authority are not reused.
const en = {
  completion: 'Filled in · current page', questions: 'Fields · current selection',
  searchDataText: 'Search submitted answers. Review state, identity and dates have separate filters.',
  searchPlaceholder: 'Search answers…', searchIn: 'Fields', all: 'All forms',
  noDrafts: 'Submitted responses only. Saving incomplete drafts is not supported.',
  combinedView: 'List and table', listView: 'Answer list', tableView: 'Data table', display: 'Display',
};
const ar = {
  title: 'إجابات النماذج', subtitle: 'راجع البيانات المقدمة وصفّ الإجابات وتحقق من الحقول المحفوظة.',
  forms: 'النماذج', submissions: 'الإجابات', questions: 'الحقول · التحديد الحالي', completion: 'الحقول المعبأة · الصفحة الحالية',
  chooseForm: 'اختر نموذجًا', selectForm: 'اختر نموذجًا للاطلاع على إجاباته.', form: 'النموذج', all: 'كل النماذج',
  submission: 'إجابة', submissionsLower: 'إجابات', field: 'حقل', fields: 'حقول',
  responseTools: 'طرق عرض الإجابات وأدواتها', responseViews: 'نوع الإجابات', completedTab: 'مكتملة',
  noDrafts: 'تعرض الإجابات المقدمة فقط. حفظ المسودات غير المكتملة غير مدعوم.',
  previous: 'السابق', next: 'التالي', page: 'الصفحة', refresh: 'تحديث', refreshing: 'جارٍ التحديث…', match: 'نتيجة', matches: 'نتائج',
  searchData: 'ابحث عن إجابة', searchDataText: 'ابحث في الإجابات المقدمة. تتوفر مرشحات مستقلة لحالة القراءة والهوية والتاريخ.',
  search: 'بحث', searchPlaceholder: 'ابحث في الإجابات…', clearSearch: 'مسح البحث', statusFilter: 'حالة القراءة',
  submissionList: 'الإجابات', submissionListText: 'اختر إجابة لمراجعتها.', submissionDetails: 'تفاصيل الإجابة',
  submissionDetailsText: 'اقرأ الحقول المحفوظة للإجابة المحددة.',
  noSelectedSubmission: 'لم تحدد إجابة', noSelectedSubmissionText: 'اختر إجابة للاطلاع على حقولها المحفوظة.',
  noAnswerPreview: 'لا تتوفر معاينة للإجابة', noDate: 'لا يوجد تاريخ', created: 'تاريخ الإرسال', submittedBy: 'مقدم الإجابة',
  guestSubmitter: 'زائر', guestRole: 'زائر', reviewStatus: 'حالة القراءة', status: 'حالة القراءة',
  emptyTitle: 'لا توجد إجابات بعد', emptyText: 'ستظهر الإجابات هنا بعد إرسال النموذج.',
  filteredEmptyTitle: 'لا توجد إجابات مطابقة', filteredEmptyText: 'لا توجد إجابات تطابق المرشحات الحالية.',
  loadingTitle: 'جارٍ تحميل الإجابات', loadingText: 'جارٍ الحصول على الإجابات المحفوظة.',
  errorTitle: 'تعذر تحميل الإجابات', errorText: 'أعد المحاولة أو تحقق من صلاحية الوصول.',
  reviewInExcel: 'فتح جدول البيانات', spreadsheetSubtitle: 'معاينة للقراءة فقط · الصفحة الحالية', closeSpreadsheet: 'إغلاق',
  spreadsheetPopupBlocked: 'اسمح بالنوافذ المنبثقة لفتح جدول البيانات.',
  combinedView: 'القائمة والجدول', listView: 'قائمة الإجابات', tableView: 'جدول البيانات', display: 'العرض',
};
export function learningResponsesContent(language) {
  return {...getResponsesContent('en'), ...en, ...(language.startsWith('ar') ? ar : {})};
}
