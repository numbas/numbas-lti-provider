function read_elements() {
    var rows = document.querySelectorAll('#initial-data tr');
    var out = [];
    for(var i=0;i<rows.length;i++) {
        var row = rows[i];
        var key = row.getAttribute('data-key');
        var time = row.querySelector('.time').textContent;
        var value = row.querySelector('.value').textContent;
        out.push({key:key,time:time,value:value});
    }

    var initial = document.querySelector('#initial-data');
    initial.parentElement.removeChild(initial);
    
    return out;
}

function DataModel(elements) {
    this.all_elements = ko.observableArray([]);
    this.keys = [];
    this.elements = {}
    elements.forEach(this.add_element,this);

    this.query = ko.observable('');
    this.most_recent_only = ko.observable(true);

    this.show_elements = ko.pureComputed(function() {
        this.all_elements();
        var query = this.query().toLowerCase();
        var re = new RegExp(query);
        var keys = this.keys.filter(re.test,re);
        keys.sort();
        var out = [];
        var most_recent = this.most_recent_only();
        keys.forEach(function(key) {
            var sorted_elements = this.elements[key].sort(function(a,b) {
                a = a.time;
                b = b.time;
                return a>b ? -1 : b>a ? 1 : 0;
            });
            if(most_recent) {
                sorted_elements = sorted_elements.slice(0,1);
            }
            out.push({key:key,elements:sorted_elements});
        },this);
        return out;
    },this);
}
DataModel.prototype = {
    add_element: function(element) {
        var key = element.key
        if(this.elements[key]) {
            this.elements[key].push(element);
        } else {
            this.keys.push(key);
            this.elements[key] = [element];
        }
        this.all_elements.push(element);
    },
    listen_for_changes: function(url) {
        var dm = this;
        var ws_scheme = window.location.protocol == "https:" ? "wss" : "ws";
        var socket = this.socket = new RobustWebSocket(ws_scheme + '://' + window.location.host + url);

        socket.onmessage = function(e) {
            var element = JSON.parse(e.data);
            dm.add_element(element);
        }
    }
}

function filter_rows(query) {
    var re = new RegExp(query);
    query = query.toLowerCase();
    var rows = document.querySelectorAll('#initial-data tr');
    Array.prototype.map.apply(rows,[function(row) {
        var key = row.getAttribute('data-key');
        row.classList.toggle('hidden',!re.test(key));
    }]);
}

document.querySelector('.search').addEventListener('click',function(e) {
    if(!e.target.classList.contains('quick-query')) {
        return;
    }
    
    dm.query(e.target.getAttribute('data-query'));
});


var dm = new DataModel(read_elements());
dm.listen_for_changes(listener_url);

ko.options.deferUpdates = true;

ko.applyBindings(dm);
