ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.contacts ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.users FROM anon;
REVOKE ALL ON public.contacts FROM anon;

REVOKE ALL ON public.users FROM authenticated;
REVOKE ALL ON public.contacts FROM authenticated;

GRANT SELECT, INSERT, UPDATE ON public.users TO authenticated;

DROP POLICY IF EXISTS users_select_own ON public.users;
DROP POLICY IF EXISTS users_insert_own ON public.users;
DROP POLICY IF EXISTS users_update_own ON public.users;
DROP POLICY IF EXISTS contacts_insert_public ON public.contacts;

CREATE POLICY users_select_own
ON public.users
FOR SELECT
TO authenticated
USING (auth_id = auth.uid());

CREATE POLICY users_insert_own
ON public.users
FOR INSERT
TO authenticated
WITH CHECK (auth_id = auth.uid());

CREATE POLICY users_update_own
ON public.users
FOR UPDATE
TO authenticated
USING (auth_id = auth.uid())
WITH CHECK (auth_id = auth.uid());
