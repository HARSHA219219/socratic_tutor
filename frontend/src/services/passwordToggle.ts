/** State of the show/hide password button (kept separate so it can be validated without a browser). */
export function passwordToggleState(visible: boolean) {
  return {
    inputType: visible ? 'text' : 'password',
    label: visible ? 'Hide password' : 'Show password',
    pressed: visible,
  } as const;
}
