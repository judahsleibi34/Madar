#!/usr/bin/env python3
"""Native-authenticated positive and adversarial tenant resource reads."""

import json
import secrets
from uuid import UUID

import manage
from smoke import application_origin, cookie_header, cookies, http, literal


def main():
    manage.require_database_marker()
    values = dict(line.split("=", 1) for line in (manage.RUNTIME / "application.env").read_text().splitlines())
    service = values["SUPABASE_SERVICE_KEY"]
    fixtures = []
    for _index in range(2):
        token = secrets.token_hex(8)
        email, password = f"tenant-isolation-{token}@example.com", secrets.token_urlsafe(24)
        auth, _ = http("POST", "/auth/v1/admin/users", token=service,
                       body={"email": email, "password": password, "email_confirm": True})
        auth_id = str(UUID(auth["id"]))
        tenant = int(manage.sql("insert into public.tenants(brand_name,owner_name) "
                                "values('Synthetic isolation','Fixture') returning tenant_id;"))
        user = int(manage.sql("insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified,email_verified_at) "
                    f"values({literal(auth_id)},'Synthetic','Tenant',{literal(email)},{tenant},'active',true,now()) returning id;"))
        manage.sql("insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status) "
                   f"values({tenant},{user},{literal(auth_id)},'owner','active');")
        project = str(UUID(manage.sql("insert into public.builder_projects(tenant_id,owner_user_id,name,slug,draft_schema) "
                    f"values({tenant},{user},'Synthetic isolation',{literal('isolation-'+token)},'{{}}') returning id;")))
        session, _ = http("POST", "/auth/v1/token?grant_type=password", body={"email": email, "password": password})
        fixtures.append({"tenant": tenant, "user": user, "project": project,
                         "cookies": {"madar_access_token": session["access_token"], "madar_refresh_token": session["refresh_token"]}})
    for index, owned in enumerate(fixtures):
        other = fixtures[1 - index]
        status,status_headers=http('GET','/auth/user_status',application=True,headers=cookie_header(owned['cookies']))
        assert status.get('logged_in') is True and status.get('csrf_token')
        owned['cookies'].update(cookies(status_headers))
        headers = cookie_header(owned["cookies"])
        listing, _ = http("GET", f"/builder/projects?tenant_id={other['tenant']}", application=True, headers=headers)
        assert {str(item["id"]) for item in listing["projects"]} == {owned["project"]}
        fetched, _ = http("GET", "/builder/projects/" + owned["project"], application=True, headers=headers)
        assert fetched["project"]["tenant_id"] == owned["tenant"]
        http("GET", "/builder/projects/" + other["project"], application=True, headers=headers, expected=(404,))
        http("GET", f"/users/{other['user']}/builder/projects", application=True, headers=headers, expected=(403,))
        http("GET", "/admin/users", application=True, headers=headers, expected=(403,))
        mutation_headers={**headers,'Origin':application_origin(),'X-CSRF-Token':status['csrf_token']}
        def project_snapshot(identifier):
            return manage.sql('select row_to_json(p)::text from public.builder_projects p where id='+literal(identifier)+';')
        foreign_before=project_snapshot(other['project'])
        http('DELETE','/builder/projects/'+other['project'],application=True,headers=mutation_headers,expected=(404,))
        assert project_snapshot(other['project'])==foreign_before
        http('DELETE',f"/users/{other['user']}/builder/projects/{owned['project']}",application=True,headers=mutation_headers,expected=(403,))
        archived,_=http('DELETE','/builder/projects/'+owned['project'],application=True,headers=mutation_headers)
        assert archived['project']['status']=='archived'
        manage.sql(f"update public.tenant_memberships set status='disabled' where tenant_id={owned['tenant']} and user_id={owned['user']};")
        # The provider JWT is still valid; current membership must deny both
        # reads and mutations rather than trusting stale session identity.
        http('GET','/builder/projects',application=True,headers=headers,expected=(403,))
        http('DELETE','/builder/projects/'+owned['project'],application=True,headers=mutation_headers,expected=(403,))
    manage.private_write("tenant-isolation-fixture.json", json.dumps([
        {key: value for key, value in item.items() if key != "cookies"} for item in fixtures], indent=2))
    print("PASS native own-project read/archive, bidirectional cross-tenant read/write denial without foreign mutation, path-user spoofing denial, tenant-query/admin rejection and immediate disabled-membership read/write denial with a valid JWT")


if __name__ == "__main__":
    main()
