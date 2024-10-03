const lockdown_fields = {
    'numbas': ['lockdown_app_password', 'show_lockdown_app_password'],
    'seb': ['seb_settings', 'show_lockdown_app_password']
};
function toggle_lockdown_fields() {
    const require_lockdown_app = document.getElementById('id_require_lockdown_app').value;
    const shown_fields = lockdown_fields[require_lockdown_app] || [];
    Object.entries(lockdown_fields).forEach(([value, fields]) => {
        for(let f of fields) {
            const show = shown_fields.indexOf(f) >= 0;
            const input = document.getElementById(`id_${f}`);
            if(!input) {
                continue;
            }
            let group = input.parentElement;
            group.classList.toggle('hidden',!show);
        }
    });
}
toggle_lockdown_fields();
document.getElementById('id_require_lockdown_app').addEventListener('input', toggle_lockdown_fields);
