/** A SCORM API.
 * It provides the `window.API_1484_11` object, which SCORM packages use to interact with the data model.
 * It tries to save data back to the server first using a websocket, before falling back to an AJAX request.
 * If all of that fails, it saves data to localStorage, so the client can resume where they left off if they come back later.
 *
 * @param {object} data - A dictionary of the SCORM data model
 * @param {number} attempt_pk - the id of the associated attempt in the database
 * @param {string} fallback_url - URL of the AJAX fallback endpoint
 */
var _ = gettext;

function SCORM_API(options) {
    var data = options.scorm_cmi;
    var sc = this;

    this.callbacks = new CallbackHandler();

    this.offline = options.offline;

    this.attempt_pk = options.attempt_pk;
    this.fallback_url = options.fallback_url;
    this.show_attempts_url = options.show_attempts_url;

    this.update_availability_dates(options,true);

    /** Key to save data under in localStorage
     */
    this.localstorage_key = 'numbas-lti-attempt-'+this.attempt_pk+'-scorm-data';

    /** A unique ID for this instance of the API, to differentiate it from other clients loading the same attempt.
     */
    this.uid = (new Date()-0)+':'+Math.random();

    /** We will store changed elements in a queue, to be sent to the server in batches periodically
     */
    this.queue = [];

    /** A dictionary of batches of elements which have been sent, but we haven't received confirmation that the server has saved them.
     *  Maps batch ids to lists of SCORMElements.
     */
    this.sent = {};
    this.element_acc = 0;

    /** An accumulator for the batch IDs
     */
    this.sent_acc = (new Date()).getTime();

    this.initialise_data(data);

    this.initialise_api();

    if(!this.offline) {
        /** Initialise the WebSocket connection
         */
        this.initialise_socket();

        /** Periodically, update the connection status display
         */
        this.update_interval = setInterval(function() {
            sc.update();
        },50);

        /** Periodically send data over the websocket
         */
        this.socket_interval = setInterval(function() {
            sc.send_queue_socket();
        },this.socket_period);

        this.ajax_period = this.base_ajax_period;

        function send_ajax_interval() {
            sc.send_ajax();
            setTimeout(send_ajax_interval,sc.ajax_period);
        }
        setTimeout(send_ajax_interval,sc.ajax_period);
    }

    this.initialise_display();
}
SCORM_API.prototype = {

    /** Interval when websocket is connected to send data over websocket, in milliseconds
     */
    socket_period: 50,

    /** Interval when websocket is disconnected to send data over AJAX, in milliseconds
     */
    base_ajax_period: 5000,

    /** Amount to multiply ajax_period by on failure
     */
    ajax_period_exponent: 1.5,

    /** How long the warning message should stay visible after the warning disappears, in milliseconds
     */
    warning_linger_duration: 1000,

    /** Has the API been initialised?
     */
	initialized: false,

    /** Has the API been terminated?
     */
	terminated: false,

    /** The code of the last error that was raised
     */
	last_error: 0,

    /** Update the availability dates for the resource
     */
    update_availability_dates: function(data,first) {
        var sc = this;
        this.allow_review_from = load_date(data.allow_review_from);
        var available_from = load_date(data.available_from);
        var available_until = load_date(data.available_until);
        var changed = !(dates_equal(available_from, this.available_from) && dates_equal(available_until, this.available_until));
        this.available_from = available_from;
        this.available_until = available_until;
        if(this.available_until) {
            Array.from(document.querySelectorAll('.available-until')).forEach(function(s) {
                s.textContent = sc.available_until.toLocaleString(DateTime.DATETIME_FULL);
            });
        }
        var deadline_change_display = document.getElementById('deadline-change-display');
        if(deadline_change_display) {
            if(changed) {
                if(!first) {
                    deadline_change_display.classList.add('show');
                }
            }
            if(!this.available_until) {
                deadline_change_display.classList.remove('show');
            }
        }

        if(data.duration_extension) {
            this.data['numbas.duration_extension.amount'] = data.duration_extension.amount;
            this.data['numbas.duration_extension.units'] = data.duration_extension.units;
            this.post_message({
                'numbas change': 'exam duration extension'
            });
        }
    },

    post_message: function(data) {
        var scorm_player = document.getElementById('scorm-player');
        if(scorm_player) {
            var scorm_window = scorm_player.contentWindow;
            scorm_window.postMessage(data);
        }
    },

    /** Bind events on the display
     */
    initialise_display: function() {
        var deadline_change_display = document.getElementById('deadline-change-display');
        if(deadline_change_display) {
            deadline_change_display.addEventListener('click',function() {
                deadline_change_display.classList.remove('show');
            });
        }
    },

    /** Setup the SCORM data model.
     *  Merge in elements loaded from the page with elements saved to localStorage, taking the most recent value when there's a clash.
     */
    initialise_data: function(data) {
        var stored_data = this.get_localstorage();

        this.sent = {};
        for(var id in stored_data.sent) {
            this.sent[id] = {
                elements: stored_data.sent[id].map(function(e) {
                    return new SCORMData(e.key,e.value,DateTime.fromSeconds(e.time));
                }),
                time: DateTime.local()
            }
        }

        // merge saved data
        for(var id in this.sent) {
            this.sent_acc = Math.max(this.sent_acc,id);

            var elements = this.sent[id].elements;
            elements.forEach(function(e) {
                var d = data[e.key];
                if(!(e.key in data) || data[e.key].time<e.timestamp()) {
                    data[e.key] = {value:e.value,time:e.timestamp()};
                }
            });
        }

        // create the data model
        this.data = {};
        for(var key in data) {
            this.data[key] = data[key].value;
        }
        
        /** SCORM display mode - 'normal' or 'review'
         */
        this.mode = this.data['cmi.mode'];

        /** Is the client allowed to change data model elements?
         *  Not allowed in review mode.
         */
        this.allow_set = this.mode=='normal';

        // Force review mode from now on if activity is completed - could be out of sync if resuming a session which wasn't saved properly.
        if(this.data['cmi.completion_status'] == 'completed') {
            if(this.allow_review_from!==null && DateTime.local()<this.allow_review_from && this.data['numbas.user_role'] != 'instructor') {
                var player = document.getElementById('scorm-player');
                if(player) {
                    player.parentElement.removeChild(player);
                }
                this.ajax_period = 0;
                this.send_ajax().then(function(m) {
                    redirect(this.show_attempts_url+'&back_from_unsaved_complete_attempt=1');
                });
            }
            this.data['cmi.mode'] = this.mode = 'review';
        }

        this.callbacks.trigger('initialise_data');
    },

    /** Initialise the SCORM API and expose it to the SCORM activity
     */
    initialise_api: function() {
        var sc = this;

        /** The API object to expose to the SCORM activity
         */
        this.API_1484_11 = {};
        ['Initialize','Terminate','GetLastError','GetErrorString','GetDiagnostic','GetValue','SetValue','Commit'].forEach(function(fn) {
            sc.API_1484_11[fn] = function() {
                return sc[fn].apply(sc,arguments);
            };
        });

        /** Counts for the various lists in the data model
         */
        this.counts = {
            'comments_from_learner': 0,
            'comments_from_lms': 0,
            'interactions': 0,
            'objectives': 0,
        }
        this.interaction_counts = [];

        /** Set the counts based on the existing data model
         */
        for(var key in this.data) {
            this.check_key_counts_something(key);
        }

        this.callbacks.trigger('initialise_api');
    },

    /** Terminate the SCORM API because we were told to by the server, and navigate to the given URL
     */
    external_kill: function(message) {
        if(!this.terminated) {
            this.Terminate('');
            alert(message);
            redirect(this.show_attempts_url);
            this.callbacks.trigger('external_kill');
        }
    },

    /** Force the exam to end.
     */
    end: function(reason) {
        if(reason!==undefined) {
            this.SetValue('x.reason ended',reason);
        }
        this.Terminate('');
        this.ended = true;
        document.body.classList.add('ended');
    },

    initialise_socket: function() {
        if(this.offline) {
            return;
        }
        var sc = this;

        var ws_scheme = window.location.protocol == "https:" ? "wss" : "ws";
        var ws_url = ws_scheme + '://' + window.location.host + "/websocket/attempt/"+this.attempt_pk+"/scorm_api?uid="+encodeURIComponent(this.uid)+"&mode="+encodeURIComponent(this.mode);

        /** A WebSocket to send data back to the server. It will automatically reconnect, but won't guarantee delivery of messages.
         */
        this.socket = new RobustWebSocket(ws_url);

        this.socket.onmessage = function(e) {
            try {
                var d = JSON.parse(e.data);
            } catch(e) {
                console.log(_("Error reading socket message"),e.data);
                return;
            }
            sc.callbacks.trigger('socket.onmessage',d);

            if(d.availability_dates) {
                sc.update_availability_dates(d.availability_dates);
            }

            // The server sends back confirmation of each batch of elements it received.
            // When we get confirmation, remove that batch from the dict of unconfirmed batches.
            if(d.received) {
                sc.batch_received(d.received);
            }

            if(sc.mode!='review' && d.current_uid && d.current_uid != sc.uid) {
                sc.external_kill(_("This attempt has been opened in another window. You may not enter any more answers here. You may continue in the other window. Click OK to leave this attempt."));
            }

            if(sc.mode!='review' && d.completion_status == 'completed') {
                sc.external_kill(_("This attempt has been ended in another window. You may not enter any more answers here. Click OK to leave this attempt."));
            }
        }

        this.socket.onopen = function() {

            // resend any batches we didn't get confirmation messages for
            for(var id in sc.sent) {
                sc.send_elements_socket(sc.sent[id].elements,id);
            }

            // send the current queue
            sc.send_queue_socket();

            sc.callbacks.trigger('socket.onopen');
        }

        this.socket.onerror = function() {
            sc.callbacks.trigger('socket.onerror');
        }
        this.socket.onclose = function() {
            sc.callbacks.trigger('socket.onclose');
        }

    },

    /** Update the connection display, and check for passing the end date
     */
    update: function() {
        var unreceived = false;
        for(var x in this.sent) {
            unreceived = true;
            break;
        }
        var queued = this.queue.length>0;
        var disconnected = !(this.socket_is_open() || this.ajax_is_working());

        var ok = !((unreceived || queued || !this.signed_receipt) && (disconnected || this.terminated)) && !this.failed_final_ajax;

        if(!ok) {
            this.last_show_warning = DateTime.local();
        }
        warning_linger_duration = this.terminated ? 0 : this.warning_linger_duration;
        var show_warning = !ok || (DateTime.local()-this.last_show_warning)<warning_linger_duration;

        var status_display = document.getElementById('status-display');

        var confirmation = this.signed_receipt !== undefined;
        if(confirmation) {
            var receipt_code_display = document.getElementById('receipt-code');
            if(receipt_code_display && receipt_code_display.textContent != this.signed_receipt) {
                receipt_code_display.textContent = this.signed_receipt;
            }
        }

        function toggle(elem,cls,on) {
            if(on) {
                elem.classList.add(cls);
            } else {
                elem.classList.remove(cls);
            }
        }

        if(status_display) {
            toggle(status_display,'ok',!show_warning);
            toggle(status_display,'ended',this.ended);
            toggle(status_display,'terminated',this.terminated && !disconnected);
            toggle(status_display,'disconnected',disconnected);
            toggle(status_display,'localstorage-used',this.localstorage_used||false);
            toggle(status_display,'confirmation', confirmation);
            toggle(status_display,'failed-final-ajax', this.failed_final_ajax);
        }

        this.callbacks.trigger('update_interval');

        if(this.mode=='normal') {
            if(!this.is_available()) {
                this.end('not available');
            }
        }
    },

    /** Is this attempt available to the student?
     *
     * @returns {boolean}
     */
    is_available: function() {
        if(this.offline) {
            return true;
        }
        var now = DateTime.local();
        if(this.available_from===undefined || this.available_until===undefined) {
            return (this.available_from===undefined || now >= this.available_from) && (this.available_until===undefined || now <= this.available_until);
        }
        if(this.available_from < this.available_until) {
            return this.available_from <= now && now <= this.available_until;
        } else {
            return now <= this.available_until || now >= this.available_from;
        }
    },

    /** Call when we send a batch of elements
     * @param {SCORMData[]} elements
     * @param {number} id
     */
    batch_sent: function(elements,id) {
        this.sent[id] = {
            elements: elements,
            time: DateTime.local()
        };
        this.set_localstorage();
        this.callbacks.trigger('batch_sent',elements,id);
    },

    /** Call when we've received confirmation that the server got the batch with the given id
     * @param {number} id
     */
    batch_received: function(id) {
        delete this.sent[id];
        this.set_localstorage();
        this.callbacks.trigger('batch_received',id);
    },

    /** Store information which hasn't been confirmed received by the server to localStorage.
     */
    set_localstorage: function() {
        if(this.offline) {
            return;
        }
        try {
            var data = {
                sent: {},
                current: this.data,
                save_time: DateTime.local().toMillis()
            }
            for(var id in this.sent) {
                data.sent[id] = this.make_batch(this.sent[id].elements);
            }
            window.localStorage.setItem(this.localstorage_key, JSON.stringify(data));
            this.localstorage_used = true;
        } catch(e) {
            this.localstorage_used = false;
        }
        this.callbacks.trigger('set_localstorage');
    },

    /** Load saved information from localStorage.
     * @returns {object} of the form `{sent: {id: [{key,value,time,counter}]}}`
     */
    get_localstorage: function() {
        if(this.offline) {
            return {sent:{}};
        }
        try {
            var stored = window.localStorage.getItem(this.localstorage_key);
            if(stored===null) {
                throw(new Error());
            } else {
                return JSON.parse(stored);
            }
        } catch(e) {
            return {sent:{}};
        }
    },

    /** For a given data model key, if it belongs to a list, update the counter for that list
     */
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

    /** Is the WebSocket connection open?
     */
    socket_is_open: function() {
        if(this.offline) {
            return false;
        }
        return this.socket.readyState==WebSocket.OPEN && Object.keys(this.sent).length==0;
    },

    /** Did the last AJAX call succeed?
     */
    ajax_is_working: function() {
        if(this.offline) {
            return false;
        }
        return this.last_ajax_succeeded===undefined || this.last_ajax_succeeded;
    },

    /** Send the queued data model elements, if any, to the server, over the websocket.
     *  If there's nothing to send or the websocket isn't connected, do nothing.
     *  A copy of the sent elements is saved in `this.sent`, so we can resend it if the server doesn't confirm it saved them.
     */
    send_queue_socket: function() {
        if(this.offline) {
            return;
        }
        if(!this.queue.length || !this.socket_is_open()) {
            return;
        }
        var id = this.sent_acc++;
        this.send_elements_socket(this.queue,id);
        this.batch_sent(this.queue.slice(),id);
        this.queue = [];
        this.callbacks.trigger('send_queue_socket');
    },

    /** Send the given list of data model elements to the server, with the given batch ID.
     *  If the socket is not open, it doesn't send.
     * @param {SCORMData[]} elements
     * @param {number} id
     * @returns {boolean} if the elements were sent.
     */
    send_elements_socket: function(elements,id) {
        if(this.offline) {
            return;
        }
        if(!this.socket_is_open()) {
            return false;
        }

        var out = this.make_batch(elements);
        this.socket.send(JSON.stringify({type:'scorm.elements', id:id, data:out}));
        this.callbacks.trigger('send_elements_socket',elements,id);
        return true;
    },

    /** Serialise a batch of elements to JSON, ready to send to the server
     * @param {SCORMData[]} elements
     * @returns {object[]}
     */
    make_batch: function(elements) {
        var out = [];
        elements.forEach(function(element) {
            var key = element.key;
            out.push(element.as_json());
        });
        return out;
    },

    /** Send the queued data model elements, as well as any unconfirmed batches, to the server over AJAX.
     * If there's no data to send, or the websocket connection is open, do nothing.
     */
    send_ajax: function(force) {
        if(this.offline) {
            return;
        }
        var sc = this;

        if(this.pending_ajax && !force) {
            return Promise.resolve('pending ajax');
        }
        if(this.queue.length) {
            var id = this.sent_acc++;
            this.batch_sent(this.queue.slice(),id);
            this.queue = [];
        }

        var stuff_to_send = false;
        var batches = {};
        var now = DateTime.local().toMillis();
        for(var key in this.sent) {
            var dt = now - this.sent[key].time;
            if(this.sent[key].elements.length && dt>this.ajax_period) {
                stuff_to_send = true;
                batches[key] = this.make_batch(this.sent[key].elements);
            }
        }
        if(!(stuff_to_send || force)) {
            return Promise.resolve('no stuff to send');
        }

        var csrftoken = getCSRFToken();

        this.pending_ajax = true;

        var request = fetch(this.fallback_url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'X-CSRFToken': csrftoken,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                batches: batches,
                complete: force
            })
        });

        request = request.then(
            function(response) {
                if(!response.ok) {
                    return new Promise(function(resolve,reject) {
                        response.text().then(function(t){
                            console.error(interpolate(_('SCORM HTTP fallback error message: %s'),[t]));
                            sc.ajax_failed(t);
                            reject(t);
                        });
                    });
                }
                sc.ajax_succeeded();
                return response.json();
            },
            function(error) {
                sc.ajax_failed(error);
                return Promise.reject(error.message);
            }
        );
        request.then(
            function(d) {
                d.received_batches.forEach(function(id) {
                    sc.batch_received(id);
                });
                if(d.signed_receipt) {
                    sc.signed_receipt = d.signed_receipt;
                }
            }
        );
        this.callbacks.trigger('send_ajax');
        return request;
    },

    ajax_succeeded: function() {
        this.pending_ajax = false;
        this.last_ajax_succeeded = true;
        this.ajax_period = this.base_ajax_period;
        this.callbacks.trigger('ajax.succeeded');
    },

    ajax_failed: function(error) {
        this.pending_ajax = false;
        console.error(_('Failed to send SCORM data over HTTP'));
        this.last_ajax_succeeded = false;
        this.ajax_period *= this.ajax_period_exponent;
        this.callbacks.trigger('ajax.failed',error.message);
    },

	Initialize: function(b) {
        this.callbacks.trigger('Initialize',b);
        if(b!='' || this.initialized || this.terminated) {
			return false;
		}
		this.initialized = true;
		return true;
	},

	Terminate: function(b) {
        var sc = this;
        this.callbacks.trigger('Terminate',b);
		if(b!='' || !this.initialized || this.terminated) {
			return false;
		}
		this.terminated = true;
        document.body.classList.add('terminated');

        /** Do one last send over HTTP, to make sure any remaining data is saved straight away.
         */
        this.send_queue_socket();
        this.send_ajax(true).catch(function(e) {
            sc.failed_final_ajax = true;
        });

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
        var changed = value!=this.data[key];
        if(changed) {
    		this.data[key] = value;
            this.check_key_counts_something(key);
            this.queue.push(new SCORMData(key,value, DateTime.local(),this.element_acc++));
        }
        this.callbacks.trigger('SetValue',key,value,changed);
	},

    Commit: function(s) {
        this.callbacks.trigger('Commit');
        return true;
    }
}

function CallbackHandler() {
    this.callbacks = {};
}
CallbackHandler.prototype = {
    on: function(key,fn) {
        if(this.callbacks[key] === undefined) {
            this.callbacks[key] = [];
        }
        this.callbacks[key].push(fn);
    },
    trigger: function(key) {
        if(!this.callbacks[key]) {
            return;
        }
        var args = Array.prototype.slice.call(arguments,1);
        this.callbacks[key].forEach(function(fn) {
            fn.apply(this,args);
        });
    }
}

/** A single SCORM data model element, with the time it was set.
 */
function SCORMData(key,value,time,counter) {
    this.key = key;
    this.value = value;
    this.time = time;
    this.counter = counter;
}
SCORMData.prototype = {
    as_json: function() {
        return {
            key: this.key,
            value: this.value,
            time: this.timestamp(),
            counter: this.counter
        }
    },

    timestamp: function() {
        return this.time.toSeconds()
    }
}

function getCSRFToken() {
    return document.querySelector('input[name="csrfmiddlewaretoken"]').value;
}

function load_date(date) {
    if(date!==null && date!==undefined) {
        return DateTime.fromISO(date);
    }
}
function dates_equal(a,b) {
    return a==null ? b==null : b!=null && a.equals(b);
}

function redirect(url) {
    function clear_beforeunload(win) {
        win.onbeforeunload = null;
        for(var i=0;i<win.frames.length;i++) {
            clear_beforeunload(win.frames[i]);
        }
    }
    clear_beforeunload(window);
    window.location = url;
}
