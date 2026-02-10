const search_input = document.getElementById('nrps-member-search');
const usernames_input = document.querySelector('[name="usernames"]');
const emails_input = document.querySelector('[name="emails"]');

function filter_members(e) {
    let query = search_input.value;
    if(e.inputType == 'insertReplacementText') {
        const pk = e.data;
        const tr = document.querySelector(`#nrps-member-table tr[data-user-id="${pk}"]`);
        if(tr) {
            query = tr.querySelector('.name').textContent;
        }
        search_input.value = query;
    }
    query = query.trim().toLowerCase();
    for(let tr of document.querySelectorAll('#nrps-member-table tr.member')) {
        const data = ['name', 'username', 'email'].map(s => tr.getAttribute(`data-${s}`));
        const matches = data.some(d => d.toLowerCase().includes(query));
        if(matches) {
            tr.classList.remove('hidden');
        } else {
            tr.classList.add('hidden');
        }
    }
}

search_input.addEventListener('input', filter_members);

function update_textarea(textarea, value, checked) {
    const values = textarea.value.split('\n').map(line => line.trim());
    if(checked) {
        if(!values.includes(value)) {
            textarea.value = (textarea.value+'\n' + value).trim();
        }
    } else {
        if(values.includes(value)) {
            textarea.value = values.filter(line => line != value).join('\n').trim();
        }
    }
}

const nrps_checkboxes = Array.from(document.querySelectorAll('input[name="nrps_applies_to"]'));

nrps_checkboxes.forEach((input) => {
    input.addEventListener('change', (e) => {
        const username = input.value;
        const email = input.dataset.email;
        update_textarea(usernames_input, username, input.checked);
        update_textarea(emails_input, email, input.checked);
    });
});
