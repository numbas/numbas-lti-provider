function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
var csrftoken = getCookie('csrftoken');

function post(url,data,form) {
    var td = $(form).parents('.part-control');
    td.addClass('fetching');
    var fd = new FormData();
    if(data) {
        for(var x in data) {
            fd.append(x,data[x]);
        }
    }
    var promise = fetch(url,{
        method: 'POST',
        credentials: 'same-origin',
        headers: {
            'X-CSRFToken': csrftoken,
            'Accept': 'application/json'
        },
        body: fd
    }).then(function(r){
        if(!r.ok) {
            throw(new Error("Response from the server was not OK."));
        }
        return r.json()
    });
    promise.finally(function() {
        td.removeClass('fetching');
    })
    return promise;
}

function describe_part_path(path) {
    var m = /^q(\d+)p(\d+)(?:g(\d+)|s(\d+))?$/.exec(path);
    if(!m) {
        return path;
    }
    var ns = m.slice(1).map(function(x){ return parseInt(x)+1; })
    var desc = 'question '+ns[0]+' part '+ns[1];
    if(m[3]!=null) {
        desc += ' gap '+ns[2];
    }
    if(m[4]!=null) {
        desc += ' step '+ns[3];
    }
    return desc;
}


