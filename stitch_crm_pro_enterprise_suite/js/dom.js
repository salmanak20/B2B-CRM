export function queryActionButtons(actions = [], textNeedles = []) {
  const nodes = [...document.querySelectorAll('button, [data-action]')];
  return nodes.filter((el) => {
    const action = el.getAttribute('data-action') || '';
    if (actions.includes(action)) return true;
    const text = (el.textContent || '').replace(/\s+/g, ' ').trim().toLowerCase();
    return textNeedles.some((needle) => text.includes(String(needle).toLowerCase()));
  });
}

export function formatCurrency(value) {
  const amount = Number(value || 0);
  return `$${amount.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}
