from django.template import Library
from django.utils.translation import gettext_lazy as _
from math import sin, cos, pi, floor, log10

register = Library()

@register.inclusion_tag('numbas_lti/score_doughnut.html')
def score_doughnut(attempt):
    questions = attempt.question_scores()

    total = sum(q.max_score for q in questions)

    inr = 4
    outr = 10

    context = {'questions': []}

    context['long_description'] = '; '.join('{raw_score}/{max_score}'.format(raw_score=q.raw_score,max_score=q.max_score) for q in questions)

    num_questions = len(questions)

    gap = 0.5/(num_questions-1) if num_questions>1 else 0

    usable_angle = pi - gap*(num_questions-1)

    def large(dan):
        return '1' if abs(dan) > pi  else '0'

    an = 0
    for i, q in enumerate(questions):
        max_score = q.max_score

        score = min(q.raw_score, max_score)

        dan = max_score/total * usable_angle
        context['stroke_width'] = 4*gap/inr if num_questions>1 else 0.5

        def pangle(x):
            return an + dan*(x/max_score) + pi

        def coords_for(x,r):
            angle = pangle(x)
            return f'{r*cos(angle)} {r*sin(angle)}'

        qcontext = {}

        answered = qcontext['answered'] = q.completion_status == 'completed'

        qcontext['correctness'] = 'incorrect' if score==0 else 'correct' if score>=max_score else 'partially correct'

        qcontext['outline_path'] = f'M {coords_for(0,inr)} A {inr} {inr} 0 {large(pangle(max_score)-pangle(0))} 1 {coords_for(max_score,inr)} L {coords_for(max_score,outr)} A {outr} {outr} 0 {large(pangle(0)-pangle(max_score))} 0 {coords_for(0,outr)} z'
        qcontext['wedge_path'] = f'M {coords_for(0,inr)} A {inr} {inr} 0 {large(pangle(score)-pangle(0))} 1 {coords_for(score,inr)} L {coords_for(score,outr)} A {outr} {outr} 0 {large(pangle(0)-pangle(score))} 0 {coords_for(0,outr)} z'

        step = 10**(max(0,floor(log10(max_score/5))))
        ticks_d = ' '.join(f'M {coords_for(i,inr)} L {coords_for(i,outr)}' for i in range(floor(step),floor(max_score),floor(step)))
        qcontext['ticks_path'] = ticks_d
        qcontext['tick_width'] = dan*inr*step/max_score/10

        qcontext['title'] = (_('Question {i}: {score}') if answered else _('Question {i}: {score} (unanswered)')).format(i=i, score=f'{score}/{max_score}')

        context['questions'].append(qcontext)

        an += dan + gap

    return context

