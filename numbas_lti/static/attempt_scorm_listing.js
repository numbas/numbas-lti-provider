import {createApp} from './vue.js';

var scorm_json = document.getElementById('scorm-elements').textContent;
var elements = JSON.parse(scorm_json);

var DateTime = luxon.DateTime;

const app = createApp({
    delimiters: ['[[', ']]'],

    data() {
        return {
            query: '',
            elements: {},
            keys: [],
            most_recent_only: false
        };
    },

    mounted() {
        elements.forEach(e => this.add_element(e));

        var ws_scheme = window.location.protocol == "https:" ? "wss" : "ws";
        var socket = this.socket = new RobustWebSocket(ws_scheme + '://' + window.location.host + listener_url);

        socket.onmessage = e => {
            var element = JSON.parse(e.data);
            this.add_element(element);
        }
    },

    computed: {
        show_elements() {
            var query = this.query.toLowerCase();
            var re;
            try {
                re = new RegExp(query);
            } catch(e) {
                return [];
            }
            var keys = this.keys.filter(k => re.test(k));
            keys.sort();
            var out = [];
            keys.forEach(function(key) {
                var sorted_elements = this.elements[key].sort(function(a,b) {
                    var at = a.time;
                    var bt = b.time;
                    var ac = a.counter;
                    var bc = b.counter;
                    // sort by time and then counter
                    return at>bt ? -1 : bt>at ? 1 : ac>bc ? -1 : bc>ac ? 1 : 0;
                });
                if(this.most_recent_only) {
                    sorted_elements = sorted_elements.slice(0,1);
                }
                out.push({key:key,elements:sorted_elements});
            },this);
            return out;
        }
    },
    
    methods: {
        add_element(element) {
            var key = element.key;
            element.time = DateTime.fromISO(element.time);
            element.time_string = element.time.toLocaleString(DateTime.DATETIME_MED_WITH_SECONDS);
            if(this.elements[key]) {
                this.elements[key].push(element);
            } else {
                this.keys.push(key);
                this.elements[key] = [element];
            }
        },
        set_query(query) {
            this.query = query;
        }
    }
});

app.mount('#app');
