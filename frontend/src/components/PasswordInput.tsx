import React, { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { passwordToggleState } from '../services/passwordToggle';

/**
 * Password field with an accessible show/hide button. All normal input props (value, onChange,
 * autoComplete, required, minLength...) pass through unchanged; only the input type toggles.
 * Not for recovery codes.
 */
const PasswordInput: React.FC<Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> & { wrapperClassName?: string }> = ({
  className = '',
  wrapperClassName = '',
  ...props
}) => {
  const [visible, setVisible] = useState(false);
  const toggle = passwordToggleState(visible);
  return (
    <div className={`relative ${wrapperClassName}`}>
      <input {...props} type={toggle.inputType} className={`${className} !pr-12`} />
      <button
        type="button"
        onClick={() => setVisible(v => !v)}
        aria-label={toggle.label}
        aria-pressed={toggle.pressed}
        title={toggle.label}
        className="icon-btn !w-9 !h-9 absolute right-1.5 top-1/2 -translate-y-1/2"
      >
        {visible ? <EyeOff size={17} /> : <Eye size={17} />}
      </button>
    </div>
  );
};

export default PasswordInput;
