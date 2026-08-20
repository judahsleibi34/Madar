-- Repair malformed onboarding default builder draft schemas created before migration 030.
-- The old scaffold put elements directly under pages[0].sections[0], which crashes PageBuilder.

with candidates as (
  select
    id,
    name,
    status,
    published_schema,
    published_version,
    case when jsonb_typeof(draft_schema) = 'object' then draft_schema else '{}'::jsonb end as schema
  from public.builder_projects
), malformed as (
  select
    id,
    coalesce(nullif(schema #>> '{pages,0,sections,0,elements,0,content}', ''), name, 'New Site') as title
  from candidates
  where status = 'draft'
    and published_schema is null
    and published_version = 0
    and schema ? 'pages'
    and schema ? 'forms'
    and (select count(*) from jsonb_object_keys(schema)) = 2
    and jsonb_array_length(case when jsonb_typeof(schema->'pages') = 'array' then schema->'pages' else '[]'::jsonb end) = 1
    and schema->'forms' = '[]'::jsonb
    and schema #>> '{pages,0,id}' = 'home'
    and schema #>> '{pages,0,name}' = 'Home'
    and schema #>> '{pages,0,path}' = '/'
    and jsonb_array_length(case when jsonb_typeof(schema #> '{pages,0,sections}') = 'array' then schema #> '{pages,0,sections}' else '[]'::jsonb end) = 1
    and (schema #> '{pages,0,sections,0}') ? 'elements'
    and not ((schema #> '{pages,0,sections,0}') ? 'layout')
    and not ((schema #> '{pages,0,sections,0}') ? 'rows')
    and schema #>> '{pages,0,sections,0,id}' = 'hero'
    and schema #>> '{pages,0,sections,0,type}' = 'hero'
    and jsonb_array_length(case when jsonb_typeof(schema #> '{pages,0,sections,0,elements}') = 'array' then schema #> '{pages,0,sections,0,elements}' else '[]'::jsonb end) = 1
    and schema #>> '{pages,0,sections,0,elements,0,id}' = 'hero-title'
    and schema #>> '{pages,0,sections,0,elements,0,type}' = 'heading'
)
update public.builder_projects bp
set draft_schema = jsonb_build_object(
    'name', malformed.title || ' Website',
    'status', 'draft',
    'activePageId', 'home',
    'activeFormId', '',
    'activeCollectionId', '',
    'activeWorkflowId', '',
    'activeRoleId', '',
    'siteChrome', jsonb_build_object('brandName', malformed.title, 'logoText', malformed.title, 'subdomain', ''),
    'theme', '{}'::jsonb,
    'pages', jsonb_build_array(
      jsonb_build_object(
        'id', 'home',
        'name', 'Home',
        'slug', '/',
        'backgroundColor', '#ffffff',
        'visibility', 'public',
        'showInNavigation', true,
        'pageType', 'main',
        'sections', jsonb_build_array(
          jsonb_build_object(
            'id', 'hero',
            'name', 'Hero',
            'mode', 'auto',
            'layout', jsonb_build_object('width', 'large', 'paddingY', 'large', 'background', '#fbfaf8', 'minHeight', 560),
            'rows', jsonb_build_array(
              jsonb_build_object(
                'id', 'hero-row',
                'layout', jsonb_build_object('columns', '1', 'align', 'center', 'gap', 'medium'),
                'columns', jsonb_build_array(
                  jsonb_build_object(
                    'id', 'hero-column',
                    'name', 'Column',
                    'layout', jsonb_build_object('align', 'left'),
                    'elements', jsonb_build_array(
                      jsonb_build_object(
                        'id', 'hero-title',
                        'type', 'heading',
                        'name', 'Heading',
                        'content', malformed.title,
                        'mode', 'auto',
                        'connectedFormId', '',
                        'action', jsonb_build_object('type', 'none', 'pageId', '', 'sectionId', '', 'formId', '', 'url', '', 'message', '', 'status', ''),
                        'position', jsonb_build_object(
                          'desktop', jsonb_build_object('x', 56, 'y', 56, 'width', 380, 'height', 96),
                          'tablet', jsonb_build_object('x', 40, 'y', 44, 'width', 320, 'height', 96),
                          'mobile', jsonb_build_object('x', 22, 'y', 34, 'width', 300, 'height', 96)
                        ),
                        'styles', jsonb_build_object('color', '#1a2744', 'backgroundColor', '', 'borderRadius', '16px', 'fontSize', '46px', 'fontWeight', '950', 'textAlign', 'left', 'lineHeight', '1.04', 'alignSelf', 'auto')
                      )
                    )
                  )
                )
              )
            ),
            'freeElements', '[]'::jsonb
          )
        )
      )
    ),
    'forms', '[]'::jsonb,
    'collections', '[]'::jsonb,
    'workflows', '[]'::jsonb,
    'roles', '[]'::jsonb,
    'users', '[]'::jsonb,
    'publish', jsonb_build_object('environment', 'local', 'lastSavedAt', '', 'lastPublishedAt', '')
  ),
  updated_at = now()
from malformed
where bp.id = malformed.id;
