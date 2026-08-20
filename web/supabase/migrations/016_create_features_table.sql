-- ============================================================
-- Create features/subscriptions table
-- ============================================================

create table if not exists public.features (
    id bigserial primary key,

    tenant_id integer not null,
    subscription_type text not null,
    plan text not null,
    builder_type text,

    payment_status text not null default 'pending',

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint features_tenant_id_fkey
        foreign key (tenant_id)
        references public.tenants (tenant_id)
        on delete cascade,

    constraint features_subscription_type_check
        check (
            subscription_type in (
                'full_platform',
                'individual_builder'
            )
        ),

    constraint features_full_platform_plan_check
        check (
            subscription_type != 'full_platform'
            or plan in (
                'starter',
                'pro',
                'business'
            )
        ),

    constraint features_individual_builder_plan_check
        check (
            subscription_type != 'individual_builder'
            or plan in (
                'basic',
                'pro',
                'premium'
            )
        ),

    constraint features_builder_type_check
        check (
            builder_type is null
            or builder_type in (
                'website',
                'forms',
                'quiz',
                'reservation',
                'reports',
                'data'
            )
        ),

    constraint features_builder_required_for_individual_check
        check (
            (
                subscription_type = 'full_platform'
                and builder_type is null
            )
            or
            (
                subscription_type = 'individual_builder'
                and builder_type is not null
            )
        )
);

-- Index for tenant lookups
create index if not exists features_tenant_id_idx
    on public.features (tenant_id);

-- Optional: prevent duplicate active/pending same subscription for same tenant
create unique index if not exists features_unique_tenant_subscription_idx
    on public.features (
        tenant_id,
        subscription_type,
        plan,
        coalesce(builder_type, 'full_platform')
    );