function SCORM_API(data,attempt_pk) {
    var sc = this;

	this.data = data;

    this.mode = data['cmi.mode'];
    this.allow_set = this.mode=='normal';

    var ws_scheme = window.location.protocol == "https:" ? "wss" : "ws";
    var socket = this.socket = new ReconnectingWebSocket(ws_scheme + '://' + window.location.host + "/websocket/attempt/"+attempt_pk+"/scorm_api");

    this.queue = [];

    socket.onmessage = function(e) {
        console.log(e.data);
    }

    socket.onopen = function() {
        sc.send_queue();
    }

    this.API_1484_11 = {};
    ['Initialize','Terminate','GetLastError','GetErrorString','GetDiagnostic','GetValue','SetValue','Commit'].forEach(function(fn) {
        sc.API_1484_11[fn] = function() {
            return sc[fn].apply(sc,arguments);
        };
    });

    this.counts = {
        'comments_from_learner': 0,
        'comments_from_lms': 0,
        'interactions': 0,
        'objectives': 0,
    }
    this.interaction_counts = [];
    for(var key in this.data) {
        this.check_key_counts_something(key);
    }

    this.interval_send_queue = setInterval(function() {
        sc.send_queue();
    },50);
}
SCORM_API.prototype = {
	initialized: false,
	terminated: false,
	last_error: 0,

    check_key_counts_something: function(key) {
        var m;
        if(m=key.match(/^cmi.(\w+).(\d+)/)) {
            var ckey = m[1];
            var n = parseInt(m[2]);
            this.counts[ckey] = Math.max(n+1, this.counts[ckey]);
            this.data['cmi.'+ckey+'._count'] = this.counts[ckey];
            if(ckey=='interactions' && this.interaction_counts[n]===undefined) {
                this.interaction_counts[n] = {
                    'objectives': 0,
                    'correct_responses': 0
                }
            }
        }
        if(m=key.match(/^cmi.interactions.(\d+).(objectives|correct_responses).(\d+)/)) {
            var n1 = parseInt(m[1]);
            var skey = m[2];
            var n2 = parseInt(m[3]);
            this.interaction_counts[n1][skey] = Math.max(n2+1, this.interaction_counts[n1][skey]);
            this.data['cmi.interactions.'+n1+'.'+skey+'._count'] = this.interaction_counts[n1][skey];
        }
    },

    send_queue: function() {
        if(!this.queue.length || this.socket.readyState!=WebSocket.OPEN) {
            return;
        }

        var seen_keys = {};
        var oqueue = [];
        for(var i=this.queue.length-1;i>=0;i--) {
            var key = this.queue[i].key;
            if(!seen_keys[key]) {
                seen_keys[key] = true;
                oqueue.push(this.queue[i]);
            }
        }
        this.socket.send(JSON.stringify(oqueue));
        this.queue = [];
    },

	Initialize: function(b) {
		if(b!='' || this.initialized || this.terminated) {
			return false;
		}
		this.initialized = true;
		return true;
	},

	Terminate: function(b) {
		if(b!='' || !this.initialized || this.terminated) {
			return false;
		}
		this.terminated = true;
		return true;
	},

	GetLastError: function() {
		return this.last_error;
	},

	GetErrorString: function(code) {
		return "I haven't written any error strings yet.";
	},

	GetDiagnostic: function(code) {
		return "I haven't written any error handling yet.";
	},

	GetValue: function(key) {
		var v = this.data[key];
        if(v===undefined) {
            return '';
        } else {
            return v;
        }
	},

	SetValue: function(key,value) {
        if(!this.allow_set) {
            return;
        }
        value = (value+'');
		this.data[key] = value;
        this.check_key_counts_something(key);
        this.queue.push({key:key,value:value});
	},

    Commit: function(s) {
        return true;
    }
}
