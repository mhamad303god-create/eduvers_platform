from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
from django.forms import formset_factory
from django.db.models import Count, Q, Max
import random
import json

from accounts.decorators import role_required
from .models import (
    Assessment, AssessmentQuestion, QuestionChoice,
    AssessmentAttempt, AssessmentAnswer
)
from .forms import AssessmentForm, AssessmentQuestionForm, QuestionChoiceFormSet, AssessmentAnswerForm

@login_required
@role_required('teacher')
def teacher_assessment_list(request):
    assessments = Assessment.objects.filter(teacher=request.user.teacherprofile)
    return render(request, 'assessments/teacher_assessment_list.html', {
        'assessments': assessments
    })

@login_required
@role_required('teacher')
def assessment_create(request):
    if request.method == 'POST':
        form = AssessmentForm(request.POST)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.teacher = request.user.teacherprofile
            assessment.save()
            messages.success(request, 'تم إنشاء التقييم بنجاح')
            return redirect('assessments:question_list', assessment_id=assessment.assessment_id)
    else:
        form = AssessmentForm()
    return render(request, 'assessments/assessment_create.html', {'form': form})

@login_required
@role_required('teacher')
def assessment_edit(request, assessment_id):
    assessment = get_object_or_404(Assessment, assessment_id=assessment_id, teacher=request.user.teacherprofile)
    if request.method == 'POST':
        form = AssessmentForm(request.POST, instance=assessment)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث التقييم بنجاح')
            return redirect('assessments:teacher_assessment_list')
    else:
        form = AssessmentForm(instance=assessment)
    return render(request, 'assessments/assessment_edit.html', {
        'form': form,
        'assessment': assessment
    })

@login_required
@role_required('teacher')
def question_list(request, assessment_id):
    assessment = get_object_or_404(Assessment, assessment_id=assessment_id, teacher=request.user.teacherprofile)
    questions = assessment.assessmentquestion_set.all()
    return render(request, 'assessments/question_list.html', {
        'assessment': assessment,
        'questions': questions
    })

@login_required
@role_required('teacher')
def question_add(request, assessment_id):
    assessment = get_object_or_404(Assessment, assessment_id=assessment_id, teacher=request.user.teacherprofile)
    if request.method == 'POST':
        question_form = AssessmentQuestionForm(request.POST)
        choice_formset = QuestionChoiceFormSet(request.POST)
        if question_form.is_valid() and choice_formset.is_valid():
            with transaction.atomic():
                question = question_form.save(commit=False)
                question.assessment = assessment
                question.order_index = assessment.assessmentquestion_set.count() + 1
                question.save()
                choice_formset.instance = question
                choice_formset.save()
            messages.success(request, 'تم إضافة السؤال بنجاح')
            return redirect('assessments:question_list', assessment_id=assessment_id)
    else:
        question_form = AssessmentQuestionForm()
        choice_formset = QuestionChoiceFormSet()
    return render(request, 'assessments/question_add.html', {
        'assessment': assessment,
        'question_form': question_form,
        'choice_formset': choice_formset
    })

@login_required
@role_required('teacher')
def question_edit(request, assessment_id, question_id):
    assessment = get_object_or_404(Assessment, assessment_id=assessment_id, teacher=request.user.teacherprofile)
    question = get_object_or_404(AssessmentQuestion, question_id=question_id, assessment=assessment)
    if request.method == 'POST':
        question_form = AssessmentQuestionForm(request.POST, instance=question)
        choice_formset = QuestionChoiceFormSet(request.POST, instance=question)
        if question_form.is_valid() and choice_formset.is_valid():
            question_form.save()
            choice_formset.save()
            messages.success(request, 'تم تحديث السؤال بنجاح')
            return redirect('assessments:question_list', assessment_id=assessment_id)
    else:
        question_form = AssessmentQuestionForm(instance=question)
        choice_formset = QuestionChoiceFormSet(instance=question)
    return render(request, 'assessments/question_edit.html', {
        'assessment': assessment,
        'question': question,
        'question_form': question_form,
        'choice_formset': choice_formset
    })

@login_required
@role_required('teacher')
def question_delete(request, assessment_id, question_id):
    assessment = get_object_or_404(Assessment, assessment_id=assessment_id, teacher=request.user.teacherprofile)
    question = get_object_or_404(AssessmentQuestion, question_id=question_id, assessment=assessment)
    if request.method == 'POST':
        question.delete()
        messages.success(request, 'تم حذف السؤال بنجاح')
        return redirect('assessments:question_list', assessment_id=assessment_id)
    return render(request, 'assessments/question_delete.html', {
        'assessment': assessment,
        'question': question
    })

@login_required
@role_required('teacher')
def assessment_publish(request, assessment_id):
    assessment = get_object_or_404(Assessment, assessment_id=assessment_id, teacher=request.user.teacherprofile)
    if assessment.status == 'draft':
        assessment.status = 'published'
        assessment.save()
        messages.success(request, 'تم نشر التقييم بنجاح')
    return redirect('assessments:teacher_assessment_list')

# Student views
@login_required
@role_required('student')
def student_assessment_list(request):
    student_profile = request.user.studentprofile
    assessments = Assessment.objects.filter(status='published').select_related(
        'subject', 'teacher__user', 'course'
    ).annotate(
        question_count=Count('assessmentquestion', distinct=True),
        attempts_done=Count(
            'assessmentattempt',
            filter=Q(assessmentattempt__student=student_profile, assessmentattempt__status='completed'),
            distinct=True
        ),
        best_score=Max(
            'assessmentattempt__percentage',
            filter=Q(assessmentattempt__student=student_profile, assessmentattempt__status='completed')
        )
    ).order_by('-created_at')
    return render(request, 'assessments/student_assessment_list.html', {
        'assessments': assessments
    })

@login_required
@role_required('student')
def assessment_detail(request, assessment_id):
    assessment = get_object_or_404(Assessment, assessment_id=assessment_id, status='published')
    student_profile = request.user.studentprofile

    # Check attempts
    attempts = AssessmentAttempt.objects.filter(
        assessment=assessment,
        student=student_profile
    ).order_by('-attempt_number')

    can_take = True
    if attempts.exists():
        last_attempt = attempts.first()
        if last_attempt.status == 'in_progress':
            return redirect('assessments:assessment_take', assessment_id=assessment_id)
        elif attempts.count() >= assessment.max_attempts:
            can_take = False

    return render(request, 'assessments/assessment_detail.html', {
        'assessment': assessment,
        'attempts': attempts,
        'can_take': can_take,
        'question_count': assessment.assessmentquestion_set.count(),
        'best_attempt': attempts.filter(status='completed').order_by('-percentage').first()
    })

@login_required
@role_required('student')
def start_attempt(request, assessment_id):
    assessment = get_object_or_404(Assessment, assessment_id=assessment_id, status='published')
    student_profile = request.user.studentprofile

    # Check if can start new attempt
    existing_attempts = AssessmentAttempt.objects.filter(
        assessment=assessment,
        student=student_profile
    )
    attempt_number = existing_attempts.count() + 1

    if attempt_number > assessment.max_attempts:
        return JsonResponse({'error': 'لقد تجاوزت الحد الأقصى للمحاولات'}, status=400)

    with transaction.atomic():
        attempt = AssessmentAttempt.objects.create(
            assessment=assessment,
            student=student_profile,
            attempt_number=attempt_number,
            status='in_progress'
        )

        # Create questions for this attempt
        questions = list(assessment.assessmentquestion_set.all())
        if not questions:
            attempt.delete()
            return JsonResponse({'error': 'لا توجد أسئلة في هذا التقييم بعد'}, status=400)
        if assessment.is_randomized:
            random.shuffle(questions)

        for order, question in enumerate(questions, 1):
            AssessmentAnswer.objects.create(
                attempt=attempt,
                question=question
            )

    return JsonResponse({'attempt_id': attempt.attempt_id})

@login_required
@role_required('student')
def assessment_take(request, assessment_id):
    assessment = get_object_or_404(Assessment, assessment_id=assessment_id, status='published')
    student_profile = request.user.studentprofile

    # Get current attempt if exists
    attempt = AssessmentAttempt.objects.filter(
        assessment=assessment,
        student=student_profile,
        status='in_progress'
    ).first()
    if not attempt:
        messages.info(request, "ابدأ محاولة جديدة أولًا.")
        return redirect('assessments:assessment_detail', assessment_id=assessment_id)

    answers = attempt.assessmentanswer_set.select_related('question').all()
    if not answers.exists():
        messages.error(request, "لا توجد أسئلة مرتبطة بهذه المحاولة.")
        return redirect('assessments:assessment_detail', assessment_id=assessment_id)

    if request.method == 'POST':
        # Save answers
        for answer in answers:
            field_name = f'question_{answer.question.question_id}'
            value = request.POST.get(field_name, '').strip()

            if answer.question.question_type in ['multiple_choice', 'true_false']:
                if value:
                    choice = QuestionChoice.objects.filter(
                        choice_id=value,
                        question=answer.question
                    ).first()
                    if choice:
                        answer.selected_choice = choice
                        answer.text_answer = ''
                        answer.is_correct = choice.is_correct
                        answer.points_earned = answer.question.points if choice.is_correct else 0
                    else:
                        answer.selected_choice = None
                        answer.is_correct = False
                        answer.points_earned = 0
                else:
                    answer.selected_choice = None
                    answer.is_correct = False
                    answer.points_earned = 0
            else:
                answer.text_answer = value
                # Keep text answers for manual grading by default
                answer.is_correct = False if value else None
                answer.points_earned = 0

            answer.save()

        attempt.end_time = timezone.now()
        attempt.time_taken = int((attempt.end_time - attempt.start_time).total_seconds())
        attempt.status = 'completed'
        attempt.save()

        # Calculate score for auto-gradable questions
        calculate_attempt_score(attempt)

        if assessment.show_results_immediately:
            messages.success(request, 'تم إرسال التقييم بنجاح')
            return redirect('assessments:assessment_results', assessment_id=assessment_id)

        messages.success(request, 'تم إرسال التقييم بنجاح. ستظهر النتائج لاحقًا.')
        return redirect('assessments:attempt_history', assessment_id=assessment_id)

    return render(request, 'assessments/assessment_take.html', {
        'assessment': assessment,
        'attempt': attempt,
        'answers': answers,
        'remaining_seconds': max(
            0,
            int((assessment.duration_minutes or 0) * 60 - (timezone.now() - attempt.start_time).total_seconds())
        ) if assessment.duration_minutes else None
    })

@login_required
@role_required('student')
def assessment_submit(request, assessment_id):
    # This is handled in assessment_take POST
    return redirect('assessments:assessment_results', assessment_id=assessment_id)

@login_required
@role_required('student')
def assessment_results(request, assessment_id):
    assessment = get_object_or_404(Assessment, assessment_id=assessment_id, status='published')
    student_profile = request.user.studentprofile

    attempt = AssessmentAttempt.objects.filter(
        assessment=assessment,
        student=student_profile,
        status='completed'
    ).order_by('-end_time').first()
    if not attempt:
        messages.info(request, 'لا توجد نتيجة مكتملة لهذا التقييم بعد.')
        return redirect('assessments:assessment_detail', assessment_id=assessment_id)

    answers = attempt.assessmentanswer_set.select_related('question', 'selected_choice').all()

    return render(request, 'assessments/assessment_results.html', {
        'assessment': assessment,
        'attempt': attempt,
        'answers': answers
    })

@login_required
@role_required('student')
def attempt_history(request, assessment_id):
    assessment = get_object_or_404(Assessment, assessment_id=assessment_id, status='published')
    student_profile = request.user.studentprofile

    attempts = AssessmentAttempt.objects.filter(
        assessment=assessment,
        student=student_profile
    ).order_by('-start_time')

    return render(request, 'assessments/attempt_history.html', {
        'assessment': assessment,
        'attempts': attempts
    })

@login_required
def save_answer(request, attempt_id):
    if request.method == 'POST':
        data = json.loads(request.body)
        attempt = get_object_or_404(AssessmentAttempt, attempt_id=attempt_id, status='in_progress')
        if attempt.student.user != request.user:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        question_id = data.get('question_id')
        answer_value = data.get('answer')

        answer = get_object_or_404(AssessmentAnswer, attempt=attempt, question_id=question_id)
        question = answer.question
        if question.question_type in ['multiple_choice', 'true_false']:
            choice = QuestionChoice.objects.filter(choice_id=answer_value, question=question).first()
            if choice:
                answer.selected_choice = choice
                answer.text_answer = ''
                answer.is_correct = choice.is_correct
                answer.points_earned = question.points if choice.is_correct else 0
            else:
                answer.selected_choice = None
                answer.is_correct = False
                answer.points_earned = 0
        else:
            answer.text_answer = (answer_value or '').strip()
            answer.is_correct = None
            answer.points_earned = 0
        answer.save()
        return JsonResponse({'status': 'saved'})
    return JsonResponse({'error': 'Invalid request'}, status=400)

def calculate_attempt_score(attempt):
    """Calculate total score for an attempt"""
    answers = attempt.assessmentanswer_set.all()
    total_earned = sum(answer.points_earned for answer in answers)
    max_possible = sum(answer.question.points for answer in answers)

    if max_possible > 0:
        score_100 = (total_earned / max_possible) * 100
    else:
        score_100 = 0

    attempt.score = round(score_100, 2)
    attempt.max_score = 100
    if max_possible > 0:
        attempt.percentage = round(score_100, 2)
        attempt.passed = attempt.percentage >= attempt.assessment.passing_score
    else:
        attempt.percentage = 0
        attempt.passed = False
    attempt.save()
