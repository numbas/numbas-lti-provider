var selected_project = null;
var query = '';

function filter_exams() {
    query = query.toLowerCase().trim();
    Array.prototype.forEach.apply(document.querySelectorAll('.available-exam'),[function(e) {
        var name = e.getAttribute('data-name');
        var project = e.getAttribute('data-project');
        var match = (selected_project==null || project==selected_project) && (query.length==0 || name.toLowerCase().indexOf(query)>=0);
        e.classList.toggle('exclude',!match);
    }]);
}


var exam_search = document.getElementById('exam-search');
exam_search.addEventListener('input',function() {
    query = exam_search.value;
    filter_exams();
});
var project_selector = document.getElementById('project-selector');
project_selector.addEventListener('change',function() {
    selected_project = project_selector.value || null;
    filter_exams();
});

