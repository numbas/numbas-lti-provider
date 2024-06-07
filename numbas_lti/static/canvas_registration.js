const preset_input = document.getElementById('id_preset');
const form = document.getElementById('canvas-form');

const presets = JSON.parse(document.getElementById('canvas-presets-json').textContent);

function update_issuer() {
    const preset_name = preset_input.value;
    form.classList.toggle('custom-preset', preset_name == 'custom');
    const preset = presets[preset_name] || {'issuer': '', 'key_set_url': '', 'auth_login_url': ''};
    Object.entries(preset).forEach(([name,value]) => {
        const input = document.getElementById(`id_${name}`);
        if(!input) {
            return;
        }
        input.value = value;
    });
}

update_issuer();
preset_input.addEventListener('change', update_issuer);
