function initialise_api(scorm_cmi) {
    var scorm_api_data = js_vars.scorm_api_data;
    scorm_api_data.scorm_cmi = scorm_cmi;
    try {
        var sc = new SCORM_API(scorm_api_data);
        window.API_1484_11 = sc.API_1484_11;
    } catch(e) {
        console.error(e);
        alert(gettext("A connection to the server could not be created. Please report this."));
        redirect_to_attempts();
    }
    if(document.readyState == 'complete') {
        load_iframe();
    } else {
        window.addEventListener('load',function() {
            load_iframe();
        });
    }
}

function redirect_to_attempts() {
    window.location.href = js_vars.scorm_api_data.show_attempts_url;
}

function load_iframe() {
    var iframe = document.createElement('iframe');
    iframe.setAttribute('id','scorm-player');
    iframe.setAttribute('width','100%');
    iframe.setAttribute('height','100%');
    iframe.setAttribute('src',js_vars.exam_url);
    var iframe_container = document.getElementById('scorm-player-container');
    iframe_container.innerHTML = '';
    iframe_container.appendChild(iframe);

    // TODO - replace with a ResizeObserver
    function resize_iframe() {
        var iframe = document.getElementById('scorm-player');
        if(!(iframe && iframe.contentWindow)) {
            return;
        }
        try {
            var dh = document.documentElement.getBoundingClientRect().bottom;
            var ih = iframe.clientHeight;
            var oh = dh-ih;
            var wh = window.innerHeight;
            var h = wh-oh-10;
            var height = Math.max(500,h);
            iframe.style.height = height+'px';
        } catch(e) {
        }
    }
    setInterval(resize_iframe,500);
}

function show_loading_error(e) {
    document.body.classList.add('terminated');
    document.getElementById('scorm-player-container').style.display = 'none';
    var status_display = document.getElementById('status-display');
    status_display.className = 'loading-error';
    console.error(e);
}

var js_vars = JSON.parse(document.getElementById('js_vars').textContent);

fetch(js_vars.cmi_url, {headers: {'Accept': 'application/json'}}).then(function(response) {
    if(response.status == 403) {
        redirect_to_attempts();
        return;
    }
    if(response.status != 200) {
        throw new Error(_("There was an error fetching the attempt data."));
    }
    response.json().then(function(data) { initialise_api(data); });
}).catch(show_loading_error);
