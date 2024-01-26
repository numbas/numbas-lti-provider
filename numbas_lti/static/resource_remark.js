import {createApp} from './vue.js';

const BATCH_SIZE = 50;

class Attempt {
    constructor(data) {
        const a = this;
        this.pk = data.pk;
        this.data = data;
        this.start_time = DateTime.fromISO(data.start_time);
        this.completion_status = data.completion_status;
        this.user = data.user;
        this.status = 'not loaded';
        this.original_raw_score = null;
        this.remarked_raw_score = null;
        this.is_changed = false;
        this.remark_error = null;
        this.fetch_error = null;

        /** possible values for status:
         * not loaded
         * loaded
         * remarking
         * remarked
         */

        this.changed_keys = {};
        this.load_data = new Promise((resolve,reject) => {
            a.load_data_resolve = resolve;
        });
    }

    get is_loaded() {
        return !(this.status=='not loaded' || this.status=='loading');
    }

    get is_remarked() {
        return this.status=='remarked';
    }

    get review_url() {
        return '/run_attempt/'+this.pk+resource_link_id_query;
    }

    get timeline_url() {
        return '/attempt/'+this.pk+'/timeline'+resource_link_id_query;
    }

    get can_save() {
        return this.status=='remarked' && this.remarked_raw_score!=this.saved_raw_score && this.status != 'saved';
    }

    get completion_status_display() {
        switch(this.completion_status) {
            case 'not attempted':
                return gettext('Not attempted');
            case 'incomplete':
                return gettext('Incomplete');
            case 'completed':
                return gettext('Complete');
        }
    }
}

const parameters_json = document.getElementById('parameters-json').textContent;
const parameters = JSON.parse(parameters_json);
const attempts_json = document.getElementById('attempts-json').textContent;
const attempts = JSON.parse(attempts_json).map(data => new Attempt(data));
const exam_source_json = document.getElementById('exam-source-json').textContent;
const exam_source = JSON.parse(exam_source_json);

const exam_window = document.getElementById('exam-iframe').contentWindow;

const ignore_keys = {
//    'cmi.suspend_data': true
};

let resource_link_id;
if(location.search) {
    const bits = location.search.slice(1).split('&');
    bits.forEach(bit => {
        const [k,v] = bit.split('=');
        if(k=='resource_link_id' || k=='lti_13_launch_id') {
            resource_link_id = bit;
        }
    });
}
const resource_link_id_query = resource_link_id ? '?'+resource_link_id : '';

const app = createApp({
    delimiters: ['[[',']]'],
    data() {
        return {
            attempts: attempts,
            apis: {},
            remarking_all: false,
            start_remark_all: new Date(),
            end_remark_all: 0,
            stopping_marking: false,
            use_unsubmitted: false,
            show_only: 'all',
            save_url: parameters['save_url'],
            saving: false,
            save_error: null,
            sort_by: 'name'
        }
    },

    mounted() {
        this.attempts.forEach(async attempt => {
            const data = await attempt.load_data;
            attempt.cmi = data.cmi;
            attempt.status = 'loaded';
            attempt.max_score = parseFloat((attempt.cmi['cmi.score.max'] || {}).value || 0);
            attempt.original_raw_score = parseFloat((attempt.cmi['cmi.score.raw'] || {}).value || 0);
            attempt.saved_raw_score = data.raw_score;
        });

        window.attempts = this.attempts;

        this.fetch_all_attempt_data();

        window.addEventListener('message',(event) => {
            this.get_remarking_results(event.data);
        });
    },

    methods: {
        stop_marking: function() {
            this.stopping_marking = true;
            this.attempts.forEach(a=>a.await_remark=false);
        },
        fetch_all_attempt_data: async function() {
            let fetch_again = true;
            while(fetch_again) {
                fetch_again = await this.fetch_attempt_data();
            }
        },
        fetch_attempt_data: async function(include_attempt) {
            const unloaded_attempts = this.attempts.filter(a=>a.status=='not loaded');
            const batch = unloaded_attempts.slice(0,BATCH_SIZE);
            if(include_attempt && include_attempt.status=='not loaded' && batch.indexOf(include_attempt)==-1) {
                batch.splice(0,1,include_attempt);
            }
            const pks = batch.map(a=>a.pk);
            if(!pks.length) { 
                return false;
            }
            let query_params = [
                'attempt_pks='+pks.join(',')
            ];
            if(resource_link_id) {
                query_params.push(resource_link_id);
            }
            try {
                const response = await fetch('remark/attempt_data?'+query_params.join('&'),{method:'GET',credentials:'same-origin'});
                const d = await response.json();
                d.cmis.forEach(cd=>{
                    const a = this.attempts.find(a=>a.pk==cd.pk);
                    a.load_data_resolve(cd);
                });
                return true;
            } catch(e) {
                batch.forEach(a=>{
                    a.fetch_error = e.message;
                    a.status = 'error';
                });
                console.error("Error getting attempt data:",e);
                return false;
            }
        },
        remark_single_attempt: function(attempt) {
            this.remarking_all = false;
            this.remark_attempt(attempt);
        },
        remark_attempt: function(attempt) {
            if(!attempt.is_loaded) {
                this.fetch_attempt_data(attempt);
            }
            if(attempt.status=='remarking') {
                return;
            }
            if(this.attempts.some(a=>a.status=='remarking')) {
                this.await_remark = true;
                return;
            }
            attempt.load_data.then(data => {
                const api = this.apis[attempt.pk] = window.API_1484_11 = new SCORM_API({
                    offline: true,
                    scorm_cmi: attempt.cmi
                });
                api.allow_set = true;
                attempt.status = 'remarking';
                attempt.await_remark = false;
                exam_window.postMessage({action:'start',pk:attempt.pk,use_unsubmitted: this.use_unsubmitted});
            });
        },

        save_single_attempt: function(attempt) {
            this.save_attempts([attempt]);
        },

        save_changed_attempts: function() {
            this.save_attempts(this.shown_attempts.filter(a=>a.can_save));
        },

        save_attempts: function(attempts) {
            var csrftoken = getCSRFToken();
            this.saving = true;

            const data = attempts.map(a=>{
                const changed_data = {}
                Object.entries(a.changed_keys).forEach(([key,value]) => {
                    changed_data[key] = value[1];
                });
                return {
                    pk: a.pk,
                    changed_keys: changed_data
                }
            });

            this.save_error = null;

            var request = fetch(this.save_url, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    attempts: data
                })
            })

            request.finally(()=>{
                this.saving = false;
            });

            request.then(r=>r.json()).then(d=>{
                if(!d.success) {
                    this.save_error = d.message;
                }
                attempts.forEach(a => {
                    a.status = d.saved.indexOf(a.pk)!=-1 ? 'saved' : 'error saving';
                    if(a.changed_keys['cmi.score.raw'] !== undefined) {
                        a.saved_raw_score = parseFloat(a.changed_keys['cmi.score.raw'][1]);
                    }
                });
            }).catch(err=>{
                this.save_error = err;
            });
        },

        get_remarking_results: function(data) {
            const pk = data.pk;
            const api = this.apis[pk];
            const attempt = this.attempts.find(a=>a.pk==pk);

            const changed_keys = {};
            attempt.is_changed = false;
            Object.keys(api.data).forEach(x=>{
                if(!ignore_keys[x] && !x.match(/\._count$/) && (attempt.cmi[x]===undefined || api.data[x]!=attempt.cmi[x].value)) {
                    attempt.is_changed = true;
                    changed_keys[x] = [attempt.cmi[x] && attempt.cmi[x].value,api.data[x]];
                }
            })
            attempt.changed_keys = changed_keys;
            attempt.remarked_raw_score = parseFloat(api.data['cmi.score.raw']);
            attempt.status = 'remarked';
            attempt.remark_success = data.success;
            attempt.remark_error = data.error;
            if(!attempt.remark_success) {
                attempt.status = 'error';
            }
            
            const next_to_remark = this.attempts.find(a=>a.await_remark);
            if(!this.stopping_marking && next_to_remark) {
                this.remark_attempt(next_to_remark);
            } else {
                this.end_remark_all = new Date();
                this.remarking_all = false;
            }
        },

        remark_all: function() {
            this.stopping_marking = false;
            this.attempts.forEach(a=> a.await_remark = true);
            const first = this.attempts[0];
            if(!first) {
                return;
            }
            this.start_remark_all = new Date();
            this.remarking_all = true;
            this.remark_attempt(first);
        }
    },
    computed: {
        num_attempts: function() { return this.attempts.length; },
        remarking_progress: function() { 
            this.end_remark_all = new Date();
            return this.attempts.filter(a=>a.is_remarked).length / this.attempts.length; 
        },
        remark_all_time: function() {
            return this.end_remark_all-this.start_remark_all;
        },
        estimated_end: function() {
            const total = this.remark_all_time/this.remarking_progress;
            return total - this.remark_all_time;
        },
        shown_attempts: function() {
            const [sort_key,sort_dir] = {
                'name': [a => a.user.full_name, 1],
                'identifier': [a => a.user.identifier, 1],
                'start_time': [a => a.start_time, -1],
                'original_score': [a => a.original_raw_score, 1],
                'saved_score': [a => a.saved_raw_score, 1],
                'completion_status': [a => ['completed','incomplete','not attempted'].indexOf(a.completion_status), 1]
            }[this.sort_by];
            function compare_attempts(a,b) {
                [a,b] = [sort_key(a), sort_key(b)];
                return (a>b ? 1 : a<b ? -1 : 0)*sort_dir;
            }
            return this.attempts.filter(a=>{
                switch(this.show_only) {
                    case 'all':
                        return true;
                    case 'completed':
                        return a.completion_status == 'completed';
                    case 'changed':
                        return a.remarked_raw_score !== null && a.saved_raw_score != a.remarked_raw_score;
                    case 'increased':
                        return a.remarked_raw_score !== null && a.original_raw_score < a.remarked_raw_score;
                    case 'decreased':
                        return a.remarked_raw_score !== null && a.original_raw_score > a.remarked_raw_score;
                }
            }).sort(compare_attempts);
        },
        num_attempts_hidden: function() {
            return this.attempts.length - this.shown_attempts.length;
        },
        changed_attempts: function() {
            return this.shown_attempts.filter(a=>a.can_save);
        }
    }
});

function todp(n,p) {
    const s = n.toFixed(p);
    return s.replace(/\.?0+$/,'')
}

app.config.globalProperties.$filters = {
    duration: function(value) {
        const d = luxon.Duration.fromMillis(value);
        return d.toFormat('mm:ss');
    },

    percent: function(value) {
        const pc = Math.floor(100*value);
        return pc;
    },

    pluralize: function(str, number) {
        return str + (Math.abs(number)==1 ? '' : 's');
    },

    dp: function(n,p) {
        if(isNaN(n) || typeof(n)!='number') {
            return n;
        }
        return todp(n,p);
    },

    datetime: function(t) {
        return t.toLocaleString(DateTime.DATETIME_MED_WITH_SECONDS);
    },
};

app.component('ScoreChange', {
    data() {
        return {}
    },
    props: ['from', 'to'],
    computed: {
        classes: function() {
            const a = this.to;
            const b = this.from;
            if(a === null) {
                return {};
            }
            return {
                'score-change': true,
                'decreased': a<b,
                'unchanged': a==b,
                'increased': a>b
            };
        },
        change: function() {
            const diff = this.to - this.from;
            const sn = todp(diff, 3)
            if(diff >= 0) {
                return '+'+sn;
            } else {
                return sn;
            }
        }
    },
    template: `
<div :class="classes">
    {{change}}
</div>`
});

app.mount('#app');

window.app = app;
