window.checkPw = function(val) {
    const rules = {
        len: val.length >= 8,
        up: /[A-Z]/.test(val),
        num: /[0-9]/.test(val),
        sym: /[^a-zA-Z0-9]/.test(val)
    };
    const metCount = Object.values(rules).filter(Boolean).length;
    
    const bars = document.querySelectorAll('.pw-bar');
    const classes = ['pw-bar--weak', 'pw-bar--fair', 'pw-bar--good', 'pw-bar--strong'];
    const currentClass = metCount >= 1 ? classes[metCount - 1] : '';
    
    bars.forEach((bar, index) => {
        bar.className = 'pw-bar' + (index < metCount ? ' ' + currentClass : '');
    });
    
    const lenRule = document.getElementById('rule-len');
    const upRule = document.getElementById('rule-up');
    const numRule = document.getElementById('rule-num');
    const symRule = document.getElementById('rule-sym');
    
    if(lenRule) lenRule.className = 'pw-rule' + (rules.len ? ' pw-rule--met' : '');
    if(upRule) upRule.className = 'pw-rule' + (rules.up ? ' pw-rule--met' : '');
    if(numRule) numRule.className = 'pw-rule' + (rules.num ? ' pw-rule--met' : '');
    if(symRule) symRule.className = 'pw-rule' + (rules.sym ? ' pw-rule--met' : '');

    const pwInput = document.getElementById('pw-input');
    if (pwInput) {
        if (metCount >= 4) {
             pwInput.classList.add('form-input--valid');
             pwInput.classList.remove('form-input--error');
        } else {
             pwInput.classList.remove('form-input--valid');
             pwInput.classList.add('form-input--error');
        }
    }

    window.dispatchEvent(new CustomEvent('password-checked', { detail: { score: metCount, valid: metCount >= 3 } }));
};

window.checkMatch = function(val) {
    const pwInput = document.getElementById('pw-input');
    const isMatch = pwInput && pwInput.value === val && val.length > 0;
    
    const pw2Input = document.getElementById('pw2-input');
    if (pw2Input) {
        if (isMatch) {
            pw2Input.classList.add('form-input--valid');
            pw2Input.classList.remove('form-input--error');
        } else if (val.length > 0) {
            pw2Input.classList.remove('form-input--valid');
            pw2Input.classList.add('form-input--error');
        } else {
            pw2Input.classList.remove('form-input--valid');
            pw2Input.classList.remove('form-input--error');
        }
    }
    
    window.dispatchEvent(new CustomEvent('password-matched', { detail: { isMatch, hasValue: val.length > 0 } }));
};
