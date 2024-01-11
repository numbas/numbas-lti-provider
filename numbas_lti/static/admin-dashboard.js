let search_autocomplete_results = [];

function select_item(item) {
    const [model, id] = item.split(':');

    const result = search_autocomplete_results.find(r => r.model == model && r.id==id);
    if(result) {
        window.location = result.url;
    }
}

const search_input = document.getElementById('global-search-input');
const search_results = document.getElementById('search-results');

let autocomplete_timeout = null;

async function autocomplete() {
    autocomplete_timeout = null;
    const query = search_input.value;
    search_results.innerHTML = '';
    const response = await fetch('/search-autocomplete?'+new URLSearchParams({query}));

    if(query != search_input.value) {
        return;
    }

    const {results} = await response.json();
    search_autocomplete_results = results;
    for(let result of results) {
        const option = document.createElement('option');
        search_results.appendChild(option);
        option.setAttribute('value', `${result.model}:${result.id}`);
        option.innerHTML = result.label;
    }
}

search_input.addEventListener('input', e => {
    if(e.inputType == 'insertReplacementText') {
        select_item(e.data);
        return;
    }

    if(autocomplete_timeout) {
        clearTimeout(autocomplete_timeout);
    }
    autocomplete_timeout = setTimeout(autocomplete, 500);
});
