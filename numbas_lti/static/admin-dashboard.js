function format_item(item) {
    return {
        value: item.text,
        text: item.text,
        html: item.label,
        url: item.url
    }
}

function select_item(e,item) {
    console.log(item);
    const data = item;
    if(data.url) {
        window.location = data.url;
    }
}


$('#search').autoComplete({
    resolverSettings: {
        url: '/search-autocomplete',
        queryKey: 'query'
    },
    minLength: 1,
    resolver: 'custom',
    events: {
        search: function (query, callback) {
            fetch('/search-autocomplete?query='+encodeURIComponent(query)).then(r=>r.json()).then(d=>{
                callback(d.results.map(format_item));
            });
        }
    }
});
$('#search').on('autocomplete.select',select_item);
