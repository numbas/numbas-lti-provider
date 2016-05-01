function SCORM_API(data) {
	this.data = data;

    var ws_scheme = window.location.protocol == "https:" ? "wss" : "ws";
    var socket = this.socket = new WebSocket(ws_scheme + '://' + window.location.host + "/scorm_api/");

    socket.onmessage = function(e) {
        console.log(e.data);
    }
    socket.onopen = function() {
        socket.send('yo')
    }
}
SCORM_API.prototype = {
	initialized: false,
	terminated: false,
	last_error: 0,

	Initialize: function(b) {
		if(b!='' || this.initialized || this.terminated) {
			return false;
		}
		this.initialized = true;
		return true;
	},

	Terminate: function() {
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

	GetValue: function(element) {
		return this.data[element];
	},

	SetValue: function(element,value) {
        console.log('set '+element+': '+value);
		this.data[element] = value;
        this.socket.send(JSON.stringify({
            element: element,
            value: value
        }));
	},

    Commit: function(s) {
        console.log("commit");
        return true;
    }
}
