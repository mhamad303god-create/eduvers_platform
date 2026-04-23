@teacher_required
def lesson_delete(request, course_id, lesson_id):
    """Delete a lesson"""
    course = get_object_or_404(Course, course_id=course_id, teacher__user=request.user)
    lesson = get_object_or_404(CourseLesson, lesson_id=lesson_id, course=course)
    
    if request.method == 'POST':
        lesson.delete()
        messages.success(request, "تم حذف الدرس بنجاح")
        return redirect('courses:course_detail', course_id=course_id)
        
    return render(request, 'courses/lesson_confirm_delete.html', {'lesson': lesson, 'course': course})
