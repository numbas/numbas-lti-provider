const BATCH_SIZE = 20;

Vue.filter('duration', function (value) {
    const d = luxon.Duration.fromMillis(value);
    return d.toFormat('mm:ss');
})

Vue.filter('percent', function (value) {
    const pc = Math.floor(100*value);
    return pc;
})

class Attempt {
    constructor(data) {
        const a = this;
        this.pk = data.pk;
        this.user = data.user;
        this.status = 'not loaded';

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
        this.load_data.then(data => {
            this.cmi = data.cmi;
            this.status = 'loaded';
            this.max_score = parseFloat((this.cmi['cmi.score.max'] || {}).value || 0);
            this.original_raw_score = parseFloat((this.cmi['cmi.score.raw'] || {}).value || 0);
        })
    }

    get is_loaded() {
        return !(this.status=='not loaded' || this.status=='loading');
    }

    get is_remarked() {
        return this.status=='remarked';
    }

    get review_url() {
        return '/run_attempt/'+this.pk;
    }
}

const attempts_json = document.getElementById('attempts-json').textContent;
const attempts = JSON.parse(attempts_json).map(data => new Attempt(data));

/*
const exam_source = JSON.parse( document.getElementById('exam-source-json').textContent);

const exam_structure = exam_source.question_groups.map(g=>{
    const gs = g.questions.map((q,qi)=>{
        const qs = {
            number: qi,
            name: q.name,
            parts: [],
            remark: true
        }
        q.parts.forEach((p,pi)=>{
            const name = p.customName || `p${pi}`;
            qs.parts.push({
                name: name,
                remark: true
            })
        });
        return qs;
    });
    return gs;
})
*/

const exam_window = document.getElementById('exam-iframe').contentWindow;

const app = new Vue({
    el: '#app',
    data: {
        attempts: attempts,
        apis: {},
        remarking_all: false,
        start_remark_all: new Date(),
        end_remark_all: 0,
        stopping_marking: false
    },
    methods: {
        stop_marking: function() {
            this.stopping_marking = true;
            this.attempts.forEach(a=>a.await_remark=false);
        },
        fetch_attempt_data: function(include_attempt) {
            const unloaded_attempts = this.attempts.filter(a=>a.status=='not loaded');
            const batch = unloaded_attempts.slice(0,BATCH_SIZE);
            if(include_attempt.status=='not loaded' && batch.indexOf(include_attempt)==-1) {
                batch.splice(0,1,include_attempt);
            }
            const pks = batch.map(a=>a.pk);
            fetch('remark/attempt_data?attempt_pks='+pks.join(','),{method:'GET',credentials:'same-origin'}).then(r=>r.json()).then(d => {
                d.cmis.forEach(cd=>{
                    const a = this.attempts.find(a=>a.pk==cd.pk);
                    a.load_data_resolve(cd);
                });
            })
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
                exam_window.postMessage({action:'start',pk:attempt.pk});
            });
        },

        get_remarking_results: function(data) {
            const pk = data.pk;
            const api = this.apis[pk];
            const attempt = this.attempts.find(a=>a.pk==pk);

            const changed_keys = {};
            Object.keys(api.data).forEach(x=>{
                if(!(x.match(/\._count$/)) && (attempt.cmi[x]===undefined || api.data[x]!=attempt.cmi[x].value)) {
                    changed_keys[x] = [attempt.cmi[x] && attempt.cmi[x].value,api.data[x]];
                }
            })
            attempt.changed_keys = changed_keys;
            attempt.remarked_raw_score = parseFloat(api.data['cmi.score.raw']);
            attempt.status = 'remarked';
            attempt.remark_success = data.success;
            
            const next_to_remark = this.attempts.find(a=>a.await_remark);
            if(!this.stopping_marking && next_to_remark) {
                this.remark_attempt(next_to_remark);
            } else {
                this.end_remark_all = new Date();
            }
        },

        remark_all: function() {
            this.stopping_marking = false;
            this.attempts.forEach(a=> a.await_remark = a.status != 'remarked');
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
        }
    }
});

window.addEventListener('message',(event) => {
    app.get_remarking_results(event.data);
});
