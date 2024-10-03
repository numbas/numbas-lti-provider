const search_input = document.getElementById('nrps-member-search');

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
