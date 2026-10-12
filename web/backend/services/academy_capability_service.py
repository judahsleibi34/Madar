"""Learning capabilities use Madar's existing commercial modules and ledger.

No new plan store: commerce funds referral/affiliate/finance capabilities;
website funds support/exchange programmes; forms funds advanced reporting.
Basic learning, optional CEFR and in-app notifications retain their existing access.
"""
from services.entitlement_service import get_tenant_entitlements, require_entitlement

CAPABILITY_REQUIREMENTS = {
    'forms': 'forms', 'affiliate': 'ecommerce', 'referrals': 'ecommerce', 'rewards': 'ecommerce',
    'wallet': 'ecommerce', 'withdrawal': 'ecommerce', 'transactions': 'ecommerce',
    'tuition': 'website_publish', 'exchange': 'website_publish', 'contact': 'website_publish', 'reports': 'data_exports',
}
SETTINGS_CAPABILITIES = {
    'affiliate_applications_enabled': 'affiliate', 'tuition_applications_enabled': 'tuition',
    'exchange_applications_enabled': 'exchange', 'exchange_opportunities_enabled': 'exchange',
    'affiliates_enabled': 'affiliate', 'affiliate_terms': 'affiliate',
    'referral_rewards_enabled': 'referrals', 'referral_reward_amount': 'referrals',
    'referral_reward_currency': 'referrals', 'referral_eligibility': 'referrals',
    'withdrawals_enabled': 'withdrawal', 'minimum_withdrawal_amount': 'withdrawal', 'withdrawal_methods': 'withdrawal',
    'tuition_support_enabled': 'tuition', 'tuition_sales_threshold': 'tuition', 'tuition_terms': 'tuition',
    'tuition_support_information_required': 'tuition', 'support_programme_name': 'tuition', 'support_eligibility': 'tuition',
    'exchange_programme_enabled': 'exchange', 'exchange_terms': 'exchange', 'exchange_programme_name': 'exchange',
}


def require_capability(tenant_id, capability):
    return require_entitlement(tenant_id, CAPABILITY_REQUIREMENTS[capability])


def capabilities(tenant_id):
    state = get_tenant_entitlements(tenant_id)
    active = set(state.get('operational_capabilities', state.get('capabilities', [])))
    return {key: not state.get('commercial_denial_code') and required in active
            for key, required in CAPABILITY_REQUIREMENTS.items()}


def validate_settings_access(tenant_id, incoming, stored):
    # Full settings forms may retain inaccessible historical configuration;
    # denial forbids changes, not saving unrelated existing learning settings.
    for key, capability in SETTINGS_CAPABILITIES.items():
        if incoming.get(key) != stored.get(key):
            require_capability(tenant_id, capability)
    if incoming.get('programmes_enabled') != stored.get('programmes_enabled'):
        from services.entitlement_service import require_any_entitlement
        require_any_entitlement(tenant_id, {'ecommerce', 'website_publish'}, message='An active academy programme entitlement is required.')


def permitted_settings(tenant_id, settings, grants=None):
    grants = capabilities(tenant_id) if grants is None else grants
    return {key: value for key, value in settings.items()
            if key not in SETTINGS_CAPABILITIES or grants[SETTINGS_CAPABILITIES[key]]}


def permitted_wallet(values, grants):
    hidden = set()
    if not grants['tuition']:
        hidden.update({'threshold', 'remaining_sales', 'tuition_eligible'})
    if not grants['exchange']:
        hidden.add('exchange_eligible')
    return {key: value for key, value in values.items() if key not in hidden}
