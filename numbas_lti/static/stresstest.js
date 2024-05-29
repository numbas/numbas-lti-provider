import {createApp} from './vue.js';

var _ = gettext;

function poisson(lambda) {
  var L = Math.exp(-lambda);
  var k = -1;
  var p = 1;
  while(p>L) {
    k += 1;
    p *= Math.random();
  }
  return k;
}

function Attempt(data) {
    this.begun = false;
    this.num_elements_set = 0;
    this.socket_state = 'closed';
    this.queue_length = 0;
    this.num_batches = 0;
    this.ajax_is_working = true;
    this.pending_ajax = false;
}
Attempt.prototype = {
    begin: function(data) {
        var a = this;
        this.begun = true;
        this.pk = data.pk;
        this.fallback_url = data.fallback_url;
        this.api = new SCORM_API({
            scorm_cmi: {'cmi.mode':{value:'normal'}},
            attempt_pk: this.pk,
            fallback_url: this.fallback_url
        });
        this.api.Initialize("");

        this.api.callbacks.on('socket.onopen',function() {
            a.socket_state = 'open';
        });
        this.api.callbacks.on('socket.onclose',function() {
            a.socket_state = 'closed';
        });
        this.api.callbacks.on('socket.onerror',function() {
            a.socket_state = 'error';
        });
        this.api.callbacks.on('SetValue',function() {
            a.num_elements_set = a.api.element_acc;
        })
        this.api.callbacks.on('update_interval',function() {
            a.queue_length = a.api.queue.length;
        });
        this.api.callbacks.on('batch_sent',function() {
            a.num_batches = Object.keys(a.api.sent).length;
        });
        this.api.callbacks.on('batch_received',function(id) {
            a.num_batches = Object.keys(a.api.sent).length;
        });
        function ajax_status() {
            a.ajax_is_working = a.api.ajax_is_working();
            a.pending_ajax = a.api.pending_ajax;
        }
        this.api.callbacks.on('send_ajax',ajax_status);
        this.api.callbacks.on('ajax.failed',ajax_status);
        this.api.callbacks.on('ajax.succeeded',ajax_status);
    },
    end: function() {
        this.ended = true;
        if(this.api) {
            this.api.Terminate("");
        }
    },
    set_element: function() {
        if(!this.api) {
            return;
        }
        var n = Math.floor(Math.random()*1000);
        var key = 'test.'+n;
        var value = Math.random()+'';
        this.api.SetValue(key,value);
    },
    ticker: function(dt,lambda) {
        var n = poisson(lambda*dt);
        for(var i=0;i<n;i++) {
            this.set_element();
        }
    }
}

const app = createApp({
    data() {
        return {
            csrftoken: getCSRFToken(),
            num_attempts_to_start: 50,
            time_to_start: '',
            start_attempts_timeout: null,
            num_elements_set_on_creation: 100,
            attempts: [],
            element_period: 60,
            last_tick: null
        }
    },

    mounted() {
        setInterval(() => {
            this.tick();
        },1000);
    },

    methods: {
        start_next_minute: function() {
            var t = new Date((new Date()).getTime()+60000);
            this.time_to_start = t.toTimeString().slice(0,5);
        },
        start_attempts: function() {
            for(var i=0;i < this.num_attempts_to_start;i++) {
                this.start_attempt();
            }
            this.time_to_start = '';
        },
        start_attempt: function() {
            let attempt = new Attempt();
            this.attempts.push(attempt);
            attempt = this.attempts[this.attempts.length-1];
            fetch('new-attempt',{
                method:'POST',
                credentials:'same-origin',
                headers:{
                    'X-CSRFToken': this.csrftoken}
            }).then(response => {
                return response.json();
            }).then(data => {
                attempt.begin(data);
                for(var i=0;i<this.num_elements_set_on_creation;i++) {
                    attempt.set_element();
                }
            }).catch(error => {
                console.error(interpolate(_("Error starting attempt: %s"),[error]));
            });
        },
        wipe: function() {
            this.attempts.forEach(attempt => attempt.end());
            fetch('wipe',{
                method:'POST',
                credentials:'same-origin',
                headers:{
                    'X-CSRFToken': this.csrftoken}
            }).then((response) => {
                this.attempts = [];
            });
        },
        tick: function() {
            var d = new Date();
            if(this.last_tick) {
                var lambda = 1/this.element_period;
                var dt = (d-this.last_tick)/1000;
                this.attempts.forEach(attempt => {
                    attempt.ticker(dt,lambda);
                });
            }
            this.last_tick = d;
        }
    },
    computed: {
        date_to_start: function() {
            var m = /(\d{2}):(\d{2})/.exec(this.time_to_start);
            if(!m) {
                return null;
            }
            var d = new Date();
            d.setHours(parseInt(m[1]));
            d.setMinutes(parseInt(m[2]));
            d.setSeconds(0);
            return d;
        },
        num_attempts_waiting_to_start: function() {
            return this.attempts.filter(a => !a.begun).length;
        },
        num_attempts_without_socket: function() {
            return this.attempts.filter(a => a.socket_state!='open').length;
        },
        num_attempts_queued: function() {
            return this.attempts.filter(a => a.queue_length>0 || a.num_batches>0).length;
        },
        num_attempts_waiting_for_ajax: function() {
            return this.attempts.filter(a => a.pending_ajax).length;
        }
    },
    watch: {
        date_to_start: function(date) {
            if(this.start_attempts_timeout) {
                clearTimeout(this.start_attempts_timeout);
            }
            if(date) {
                var seconds = date - (new Date());
                if(seconds>0) {
                    this.start_attempts_timeout = setTimeout(() => {
                        this.start_attempts();
                    },seconds);
                }
            }
        }
    }
});

app.config.globalProperties.$filters = {
    pluralize: function(n,word,plural) {
        if(n==1) {
            return word;
        } else {
            return plural || word+'s';
        }
    }
}

app.mount('#app');
