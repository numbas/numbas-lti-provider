var DateTime = luxon.DateTime;

var completed_toggle = document.getElementById('completed-toggle');

var data = JSON.parse(document.getElementById('data-json').textContent);
var only_completed = false;

var question_scores_svg = d3.select("#question_scores_chart .chart").append('svg');
var question_scores_g = question_scores_svg.append('g');
question_scores_g.append('g').attr('class','x-axis');
question_scores_g.append('g').attr('class','x-axis-top');
question_scores_g.append('g').attr('class','y-axis');

function update_completion_table() {
    var values = document.querySelectorAll('#completion-table .value');
    for(var i=0;i<values.length;i++) {
        var td = values[i];
        var value = td.getAttribute('data-value');
        var n = data.attempts.filter(function(a) { return a.completion_status==value; }).length;
        td.textContent = n;
    }
}

function update_summary_stats_table() {
    function format_duration(d) {
        d = luxon.Duration.fromMillis(d);
        if(d.as('minutes')<120) {
            return d.toFormat('m')+' minutes';
        } else if(d.as('hours')<48) {
            return d.toFormat('h')+' hours';
        } else {
            return d.toFormat('d')+' days';
        }
    }
    function timeFormat(t) {
        console.log(t);
        return t!==undefined ? DateTime.fromMillis(t).toLocaleString(DateTime.DATETIME_SHORT) : '';
    }
    function percentFormat(s) {
        return s!==undefined ? d3.format('.0%')(s) : '';
    }
    var attempts = data.attempts;
    if(only_completed) {
        attempts = attempts.filter(a=>a.completion_status=='completed');
    }
    var stats = [
        {label: 'Total score', values: attempts.map(a=>a.scaled_score).sort(d3.ascending), format: percentFormat},
        {label: 'Start time', values: attempts.map(a=>a.start_time).sort(d3.ascending), format: timeFormat},
        {label: 'End time', values: attempts.filter(a=>a.end_time).map(a=>a.end_time).sort(d3.ascending), format: timeFormat},
        {label: 'Time taken', values: attempts.filter(a=>a.end_time).map(a=>a.end_time-a.start_time).sort(d3.ascending), format: format_duration}
    ];
    var table = d3.select('#summary-stats-table')
    var rows = table.select('tbody').selectAll('tr').data(stats)
        .join(enter => {
            const tr = enter.append('tr');
            tr.append('th');
            tr.append('td')
                .attr('class','mean');
            tr.append('td')
                .attr('class','q1');
            tr.append('td')
                .attr('class','median');
            tr.append('td')
                .attr('class','q3');
            return tr;
        })
    ;
    rows.select('th').join('th')
        .text(d=>d.label)

    rows.select('td.mean')
        .text(d=>d.format(d3.mean(d.values)))
    ;

    rows.select('td.q1')
        .text(d=>d.format(d3.quantile(d.values,0.25)))
    ;

    rows.select('td.median')
        .text(d=>d.format(d3.median(d.values)))
    ;

    rows.select('td.q3')
        .text(d=>d.format(d3.quantile(d.values,0.75)))
    ;

}

function cmp(a,b) {
    return a<b ? -1 : a>b ? 1 : 0;
}

function question_label(n) {
    return 'Q'+(parseInt(n)+1);
}

function update_question_scores_chart() {
    var numbers = {};
    data.questions.forEach(function(q) {
        numbers[q.number] = true;
    });
    var attempts = data.attempts;
    if(only_completed) {
        attempts = attempts.filter(a=>a.completion_status=='completed');
    }

    // Get the different categories and count them
    var categories = Object.keys(numbers).map(n=>parseInt(n)).sort(cmp);
    var n = categories.length;

    var svg_el = document.querySelector('#question_scores_chart .chart');

    var bar_height = 120;

    // set the dimensions and margins of the graph
    var margin = {top: 40, right: 30, bottom: 20, left: 30},
        width = svg_el.getBoundingClientRect().width - margin.left - margin.right,
        height = bar_height*n;

    question_scores_svg
        .attr('width',width+margin.left+margin.right)
        .attr('height',height+margin.top+margin.right)
       
    question_scores_g
        .attr("transform",
              "translate(" + margin.left + "," + margin.top + ")")
    ;

    var x = d3.scaleLinear()
        .domain([-0.02, 1])
        .range([ 0, width ]);

    var yHeight = height/n;
    var y = d3.scaleLinear()
        .domain([-1, 1])
        .range([yHeight/2,-yHeight/2]);

    question_scores_g.select('.x-axis')
        .attr("transform", "translate(0," + height + ")")
        .call(d3.axisBottom(x)
            .tickValues([0,0.2,0.4,0.6,0.8,1])
            .tickSize(-height)
            .tickFormat(d3.format('.0%'))
        )
        .select('.domain').remove()
    ;
    question_scores_g.select('.x-axis-top')
        .attr("transform", 'translate(0,0)')
        .call(d3.axisTop(x)
            .tickValues([0,0.2,0.4,0.6,0.8,1])
            .tickSize(0)
            .tickFormat(d3.format('.0%'))
        )
        .select('.domain').remove()
    ;

    var yName = d3.scalePoint()
        .domain(['Total'].concat(categories.map(question_label)))
        .range([yHeight/2, height-yHeight*0.3])
    ;
    question_scores_g.select('.y-axis')
        .call(d3.axisLeft(yName).tickSize(-width))
        .select('.domain').remove()
    ;

    function cumulative_path(scores) {
        scores = scores.slice().sort(cmp).reverse();
        var density = [[1,0]];
        var os = 1;
        var ot = 0;
        scores.forEach(function(s,t) {
            if(s!=os) {
                density.splice(0,0,[s,t/attempts.length],[os,t/attempts.length]);
                os = s;
            }
        });
        density.splice(0,0,[0,0],[0,1]);
        return density;
    }

    var allDensity = [];
    for (i = 0; i < n; i++) {
        var number = categories[i];
        key = question_label(number);
        var qs = data.questions.filter(function(q){return q.number==number}).map(function(q){ return q.scaled_score; });
        var density = cumulative_path(qs);
        allDensity.push({key: key, density: density, number: number});
    }
    allDensity.push({key: 'Total', density: cumulative_path(attempts.map(function(a) { return a.scaled_score; }))});

    var question_colour = function(d) { return d.key=='Total' ? '#eee' : d3.schemeCategory10[d.number%10]; }
    var circle_colour = function(d) { return d.key=='Total' ? '#555' : d3.schemeCategory10[d.number%10]; }

    var bgs = question_scores_g.selectAll('.question-bg').data(allDensity);
    bgs.enter()
        .append('rect')
        .attr('class','question-bg')
        .attr('x',x(0))
        .attr('y',function(d) { return yName(d.key)+y(1) })
        .attr('width',x(1)-x(0))
        .attr('height',-y(1))
    ;
    bgs
        .attr('x',x(0))
        .attr('width',x(1)-x(0))

    // Add areas
    var areas = question_scores_g.selectAll(".question-curve")
        .data(allDensity)
    ;
    window.y = y;
    window.yName = yName;

    areas.enter()
        .append("path")
        .attr('class','question-curve')
        .attr("transform", function(d){return "translate(0," + yName(d.key) +")" })
        .attr("fill", question_colour)
        .datum(function(d){return(d.density)})
        .attr("stroke", "#000")
        .attr("stroke-width", 2)
        .attr("d",  d3.line()
            .x(function(d) { return x(d[0]); })
            .y(function(d) { return y(d[1]); })
        )
    ;
    areas
        .datum(function(d){return(d.density)})
        .attr("d",  d3.line()
            .x(function(d) { return x(d[0]); })
            .y(function(d) { return y(d[1]); })
        )
    ;

    areas.exit().remove();

    var dotYNoise = d3.randomUniform(yHeight*0.1,yHeight*0.2);

    var circle_data = 
        data.questions.map(function(q){ return {key: question_label(q.number), scaled_score: q.scaled_score, number: q.number} })
        .concat(attempts.map(function(a){ return {key: 'Total', scaled_score: a.scaled_score} }))
    ;

    var circles = question_scores_g.selectAll('.question-dot')
        .data(circle_data)
    ;
    circles
        .enter()
        .append('circle')
        .attr('class','question-dot')
        .attr('cx',function(d) { return x(d.scaled_score); })
        .attr('cy',function(d) { return yName(d.key)+dotYNoise(); })
        .attr('fill',circle_colour)
        .attr('r',1.5)
    ;
    circles
        .transition()
        .duration(1000)
        .attr('cx',function(d) { return x(d.scaled_score); })
    ;
}

function update_status_chart() {
    var numbers_dict = {};
    data.questions.forEach(function(q) {
        numbers_dict[q.number] = true;
    });
    var numbers = Object.keys(numbers_dict).map(n=>parseInt(n)).sort(cmp);

    var n = numbers.length;

    var qdata = [];
    numbers.forEach(function(n) {
        var qs = data.questions.filter(q => q.number==n);
        qdata.push({
            number: n,
            label: question_label(n),
            num_correct: qs.filter(q => q.scaled_score==1).length,
            num_partial: qs.filter(q => q.scaled_score!=0 && q.scaled_score!=1).length,
            num_incorrect: qs.filter(q => q.scaled_score==0).length,
            num_not_attempted: Math.max(0,data.attempts.length - qs.length)
        });
    });

    var format = d3.format('.0%');
    var num_attempts = data.attempts.length;

    var keys = ['num_not_attempted','num_incorrect','num_partial','num_correct'];
    var stack = d3.stack().keys(keys)(Object.values(qdata));

    var el = document.getElementById('stacked_status_chart');
    var bar_height = 25;
    var text_height = 8;
    var height = (2*bar_height+text_height)*qdata.length;
    var width = el.getBoundingClientRect().width;
    var gap = 24;

    var svg = d3.select('#stacked_status_chart svg.diagram')
        .attr('width',width)
        .attr('height',height)
        .attr('viewBox',`-40 0 ${width+50} ${height}`)
    ;

    var layers = svg.selectAll('.layer').data(stack).join(e=>e.append('g')
        .attr('class',d=>d.key)
        .classed('layer',true))
        .attr('transform',d => `translate(${gap*d.index},0)`)
        .attr('title',d => d.key)
    ;

    var y = d3.scalePoint()
        .domain(qdata.map(d=>d.label))
        .range([bar_height/2+2*text_height,height-bar_height/2])
    ;

    var x = d3.scaleLinear()
        .domain([0,num_attempts])
        .range([gap,width-gap*(keys.length-1)]);

    svg.append('g')
        .call(d3.axisLeft(y).tickSize(0))
        .attr('font-size',16)
        .select('.domain').remove()
    ;

    var sections = layers.selectAll('.section').data(d=>d).join(e=>{
        var g = e.append('g').attr('class','section');
        g.append('rect');
        g.append('text').attr('class','percentage');
        return g;
    });
    sections.selectAll('rect').data(d=>[d])
        .attr('x',d => x(d[0]))
        .attr('y',d => y(d.data.label)-bar_height/2)
        .attr('width', d => x(d[1]) - x(d[0]))
        .attr('height', bar_height)
    ;
    sections.selectAll('text.percentage').data(d=>[d])
        .attr('x',d => x((d[0]+d[1])/2))
        .attr('y',d => y(d.data.label)-bar_height/2-text_height)
        .text(d=>format((d[1]-d[0])/num_attempts))
    ;

}

function update_time_chart() {
    const margin = {top: 20, right: 20, bottom: 50, left: 40};

    var svg_el = document.querySelector('#times > .chart > .diagram');
    const width = svg_el.getBoundingClientRect().width - margin.left - margin.right;
    const height = 400;

    const [first,last] = d3.extent(data.attempts,d=>d.start_time);

    const intervals = [
        d3.timeMonth,
        d3.timeWeek,
        d3.timeDay,
        d3.timeHour
    ];
    const interval = intervals.find(i=>i.count(first,last)>=20) || intervals[intervals.length-1];

    const thresholds = interval.range(
        interval.offset(interval.floor(first),-1),
        interval.offset(interval.ceil(last),1)
    );

    const x = d3.scaleTime(d3.extent(thresholds),[margin.left,width-margin.right]);
    x.clamp(true);
    const y = d3.scaleLinear([0,data.attempts.length],[height-margin.bottom,margin.top]);
    const y_tooltip = d3.scaleLinear([0,1],[height-margin.bottom,margin.top]);

    function time_format(t) {
        var t2 = DateTime.fromJSDate(t);
        if(t2.hour==0 && t2.minute==0) {
            return t2.toLocaleString(DateTime.DATE_SHORT);
        } else {
            return t2.toLocaleString(DateTime.DATETIME_SHORT);
        }
    }

    const xAxis = g => g
        .attr("transform", `translate(0,${height - margin.bottom})`)
        .call(d3.axisBottom(x).ticks(6).tickSizeOuter(0).tickFormat(time_format))
    ;

    yAxis = g => g
        .attr("transform", `translate(${margin.left},0)`)
        .call(d3.axisLeft(y).tickFormat(d3.format('d')).tickValues(y.ticks().filter(t=>Number.isInteger(t))))
    ;

    const svg = d3.select(svg_el)
      .attr("viewBox", [0, 0, width, height])
    ;

    function key(a) {
        if(!a.end_time) {
            return a.start_time-0;
        } else {
            return ((a.end_time-0)+(a.start_time-0))/2;
        }
    }

    const sorted_attempts = data.attempts.slice().sort(function(a,b){return d3.ascending(key(a),key(b))});
    sorted_attempts.forEach(function(a,i) { a.pos = i; });

    function pinline(selection) {
        selection.select('circle.start')
            .attr('cx',d=>x(d.start_time))
            .attr('cy',d=>y(d.pos))
        ;
        selection.select('circle.end')
            .attr('opacity',d=>d.end_time ? 1 : 0)
            .attr('cx',d=>x(d.end_time || d.start_time))
            .attr('cy',d=>y(d.pos))
        ;
        selection.select('line')
            .attr('opacity',d=>d.end_time ? 1 : 0)
            .attr('x1',a=>x(a.start_time))
            .attr('y1',a=>y(a.pos))
            .attr('x2',a=>x(a.end_time || a.start_time))
            .attr('y2',a=>y(a.pos))
        ;
    }

    svg.append("g")
        .selectAll("g")
        .data(sorted_attempts)
        .join(enter => {
            const g = enter.append('g');
            g.append('circle')
                .attr('class','start')
            ;
            g.append('circle')
                .attr('class','end')
            ;
            g.append('line')
                .attr('class','duration')
            ;
            return g;
        })
        .call(pinline)
    ;

    svg.append("g")
      .call(xAxis);

    const tip = svg.append('g')
        .attr('class','tip')
        .attr('opacity',0)
    ;

    const line_tip = tip.append('line')
        .attr('x1',0)
        .attr('x2',0)
        .attr('y1',y_tooltip(0))
        .attr('y2',y_tooltip(1))
    ;
    const time_tip = tip.append('text')
        .attr('x',0)
        .attr('y',y_tooltip(1)-5)
        .attr('text-anchor','middle')
    ;

    svg.on('mouseover',function() {
        tip.transition().duration(100).attr('opacity',1);
    })
    svg.on('mouseout',function() {
        tip.transition().duration(500).attr('opacity',0);
    })
    svg.on('mousemove',function() {
        let [mx,my] = d3.mouse(this);
        mx = x(x.invert(mx));
        const t = x.invert(mx);
        time_tip.text(DateTime.fromJSDate(t).toLocaleString(DateTime.DATETIME_SHORT));
        const b_tip = time_tip.node().getBoundingClientRect();
        const tx = Math.min(Math.max(mx,b_tip.width/2),width-b_tip.width/2);
        time_tip.attr('transform',`translate(${tx},0)`);
        line_tip.attr('transform',`translate(${mx},0)`);
    });
}


function update() {
    only_completed = completed_toggle.checked;
    data.attempts.forEach(function(a) {
        a.start_time = DateTime.fromISO(a.start_time)
        a.end_time = a.end_time ? DateTime.fromISO(a.end_time) : null;
    });
    update_completion_table();
    update_summary_stats_table();
    update_question_scores_chart();
    update_status_chart();
    update_time_chart();
}

function init_socket() {
    var ws_scheme = window.location.protocol == "https:" ? "wss" : "ws";
    var ws_url = ws_scheme + '://' + window.location.host + window.location.pathname + "/websocket";

    var socket = new RobustWebSocket(ws_url);
    socket.onmessage = function(e) {
        data = JSON.parse(e.data);
        update();
    }
    socket.onopen = function() {
    }
}
init_socket();
update();
window.addEventListener('resize',function(r) {
    update();
});

completed_toggle.addEventListener('change',function() {
    update();
})
