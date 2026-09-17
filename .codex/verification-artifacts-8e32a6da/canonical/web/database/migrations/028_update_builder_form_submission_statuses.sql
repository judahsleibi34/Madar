/* ============================================================
   026_update_builder_form_submission_statuses.sql

   Purpose:
   - Persist builder form submission statuses as normalized lowercase values.
   - Preserve distinct Contacted and Closed states for authenticated response workflows.
   ============================================================ */

begin;

alter table if exists public.builder_form_submissions
  drop constraint if exists builder_form_submissions_status_check;

update public.builder_form_submissions
set status = case lower(status)
  when 'new' then 'new'
  when 'reviewed' then 'contacted'
  when 'contacted' then 'contacted'
  when 'closed' then 'closed'
  when 'spam' then 'spam'
  when 'archived' then 'archived'
  else 'new'
end;

alter table if exists public.builder_form_submissions
  add constraint builder_form_submissions_status_check
  check (status in ('new', 'contacted', 'closed', 'spam', 'archived'));

notify pgrst, 'reload schema';

commit;
