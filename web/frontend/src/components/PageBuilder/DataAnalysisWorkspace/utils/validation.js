import { toLabel } from './formatters';

export const getMissingRequiredParams = (template, params, activeLang = 'en', optionalFields = []) => {
  return Object.entries(template || {})
    .filter(([key, defaultValue]) => {
      const value = params?.[key];

      const isOptional =
        optionalFields.includes(key) ||
        key.includes('group') ||
        key.includes('category') ||
        key.includes('expense_column') ||
        key.includes('transaction_id') ||
        key.includes('numerator') ||
        key.includes('denominator') ||
        key === 'rows' ||
        key === 'max_rating' ||
        key === 'separator' ||
        defaultValue === 'profit';

      if (isOptional) return false;

      if (Array.isArray(value)) return value.length === 0;
      return value === '' || value === null || value === undefined;
    })
    .map(([key]) => toLabel(key, activeLang));
};
