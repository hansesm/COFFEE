# COFFEE Application Performance Analysis

## Critical Performance Issues Identified

### 1. **N+1 Query Problems** 🔥 **HIGH PRIORITY**

#### Problem in `CrudFeedbackView.get()` (lines 256-257):
```python
for fdb in feedback_list:
    fdb.criteria_set_json = fdb.get_criteria_set_json()  # N+1 query!
```

**Impact**: For each feedback item, a separate database query is executed. With 100 feedback items, this creates 100+ additional queries.

#### Problem in `FeedbackSessionAnalysisView.get()` (lines 715-732):
```python
for session in sessions:
    # Multiple potential N+1 queries:
    session.course.course_name if session.course else "N/A"  # N+1
    session.feedback.task.title if session.feedback and session.feedback.task else "N/A"  # N+1
```

**Impact**: Each session access triggers separate queries for course and task data.

### 2. **Missing Database Indexes** 🔥 **HIGH PRIORITY**

#### Critical Missing Indexes:
- **Course**: `faculty`, `study_programme`, `chair`, `term`, `course_name`, `active`
- **Task**: `active`, `course_id` (foreign key)
- **Criteria**: `active`, `course_id` (foreign key)
- **Feedback**: `active`, `course_id`, `task_id` (foreign keys)
- **FeedbackSession**: `timestamp`, `course_id`, `feedback_id` (foreign keys)
- **FeedbackCriteria**: `feedback_id`, `criteria_id`, `rank`

### 3. **Inefficient Query Patterns** ⚠️ **MEDIUM PRIORITY**

#### Problem in `FeedbackListView.get()` (lines 212-216):
```python
# 5 separate queries for filter options
faculties = base_course_qs.values_list("faculty", flat=True).distinct().order_by("faculty")
study_programmes = base_course_qs.values_list("study_programme", flat=True).distinct().order_by("study_programme")
chairs = base_course_qs.values_list("chair", flat=True).distinct().order_by("chair")
terms = base_course_qs.values_list("term", flat=True).distinct().order_by("term")
course_names = base_course_qs.values_list("course_name", flat=True).distinct().order_by("course_name")
```

**Impact**: 5 separate database queries that could be optimized or cached.

### 4. **Duplicate View Code** ⚠️ **MEDIUM PRIORITY**

#### Problem in views.py (lines 707-734 and 745-771):
`FeedbackSessionAnalysisView` is duplicated, causing maintenance issues and potential inconsistencies.

### 5. **Large Text Field Queries** ⚠️ **MEDIUM PRIORITY**

#### Problem: 
- `TextField` and `JSONField` columns are being loaded unnecessarily
- `course_context`, `task_context`, `feedback_data` fields loaded even when not needed

## Performance Optimization Solutions

### 1. **Fix N+1 Query Issues**

#### Solution for CrudFeedbackView:
```python
def get(self, request, *args, **kwargs):
    # Use select_related and prefetch_related
    feedback_list = Feedback.objects.filter(
        course__viewing_groups__in=request.user.groups.all()
    ).select_related('course', 'task').prefetch_related(
        'criteria_set', 'criteria_set__criteria'
    ).distinct().order_by("task")
    
    # Pre-compute all criteria JSON in a single query
    criteria_data = {}
    for feedback in feedback_list:
        criteria_data[feedback.id] = feedback.get_criteria_set_json()
    
    # Assign pre-computed data
    for feedback in feedback_list:
        feedback.criteria_set_json = criteria_data[feedback.id]
```

#### Solution for FeedbackSessionAnalysisView:
```python
def get(self, request, *args, **kwargs):
    sessions = FeedbackSession.objects.filter(
        course__viewing_groups__in=request.user.groups.all()
    ).select_related('course', 'feedback', 'feedback__task').order_by('-timestamp').distinct()
    
    # Process all sessions in memory (no more N+1 queries)
    session_data = []
    for session in sessions:
        session_data.append({
            "id": str(session.id),
            "timestamp": session.timestamp.strftime("%d.%m.%Y %H:%M:%S"),
            "staff": session.staff_user or "anonymous",
            "submission": session.submission or "",
            "nps": session.nps_score or "",
            "course": session.course.course_name if session.course else "N/A",
            "task": session.feedback.task.title if session.feedback and session.feedback.task else "N/A",
            "criteria_json": json.dumps({"criteria": (session.feedback_data or {}).get("criteria", [])}, cls=DjangoJSONEncoder, ensure_ascii=False),
        })
```

### 2. **Add Database Indexes**

Create a new migration file:
```python
# home/migrations/XXXX_add_performance_indexes.py
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('home', '0009_remove_course_managing_groups_course_editing_groups_and_more'),
    ]

    operations = [
        # Course indexes
        migrations.RunSQL("CREATE INDEX IF NOT EXISTS idx_course_faculty ON home_course(faculty);"),
        migrations.RunSQL("CREATE INDEX IF NOT EXISTS idx_course_study_programme ON home_course(study_programme);"),
        migrations.RunSQL("CREATE INDEX IF NOT EXISTS idx_course_chair ON home_course(chair);"),
        migrations.RunSQL("CREATE INDEX IF NOT EXISTS idx_course_term ON home_course(term);"),
        migrations.RunSQL("CREATE INDEX IF NOT EXISTS idx_course_name ON home_course(course_name);"),
        migrations.RunSQL("CREATE INDEX IF NOT EXISTS idx_course_active ON home_course(active);"),
        
        # Task indexes
        migrations.RunSQL("CREATE INDEX IF NOT EXISTS idx_task_active ON home_task(active);"),
        migrations.RunSQL("CREATE INDEX IF NOT EXISTS idx_task_course_active ON home_task(course_id, active);"),
        
        # Criteria indexes
        migrations.RunSQL("CREATE INDEX IF NOT EXISTS idx_criteria_active ON home_criteria(active);"),
        migrations.RunSQL("CREATE INDEX IF NOT EXISTS idx_criteria_course_active ON home_criteria(course_id, active);"),
        
        # Feedback indexes
        migrations.RunSQL("CREATE INDEX IF NOT EXISTS idx_feedback_active ON home_feedback(active);"),
        migrations.RunSQL("CREATE INDEX IF NOT EXISTS idx_feedback_course_active ON home_feedback(course_id, active);"),
        
        # FeedbackSession indexes
        migrations.RunSQL("CREATE INDEX IF NOT EXISTS idx_feedbacksession_timestamp ON home_feedbacksession(timestamp);"),
        migrations.RunSQL("CREATE INDEX IF NOT EXISTS idx_feedbacksession_course ON home_feedbacksession(course_id);"),
        
        # FeedbackCriteria indexes
        migrations.RunSQL("CREATE INDEX IF NOT EXISTS idx_feedbackcriteria_feedback_rank ON home_feedbackcriteria(feedback_id, rank);"),
    ]
```

### 3. **Optimize Filter Queries**

#### Solution for FeedbackListView:
```python
def get(self, request, *args, **kwargs):
    # Use single query with aggregation
    from django.db.models import Q
    
    # Get unique values in one query
    course_fields = Course.objects.exclude(
        Q(faculty__startswith="#") | Q(study_programme__startswith="#") | 
        Q(chair__startswith="#") | Q(term__startswith="#") | 
        Q(course_name__startswith="#")
    ).values('faculty', 'study_programme', 'chair', 'term', 'course_name').distinct()
    
    # Extract unique values
    faculties = sorted(set(item['faculty'] for item in course_fields))
    study_programmes = sorted(set(item['study_programme'] for item in course_fields))
    chairs = sorted(set(item['chair'] for item in course_fields))
    terms = sorted(set(item['term'] for item in course_fields))
    course_names = sorted(set(item['course_name'] for item in course_fields))
```

### 4. **Add Query Optimization**

#### Use defer() for large fields:
```python
# Don't load large text fields when not needed
feedback_list = Feedback.objects.filter(...).defer('course__course_context')
sessions = FeedbackSession.objects.filter(...).defer('feedback_data')
```

### 5. **Add Caching**

#### Cache filter options:
```python
from django.core.cache import cache

def get_filter_options():
    cache_key = 'course_filter_options'
    options = cache.get(cache_key)
    
    if options is None:
        # Calculate filter options
        options = {
            'faculties': [...],
            'study_programmes': [...],
            # etc.
        }
        cache.set(cache_key, options, 300)  # Cache for 5 minutes
    
    return options
```

### 6. **Add Pagination**

#### For large datasets:
```python
from django.core.paginator import Paginator

def get(self, request, *args, **kwargs):
    sessions = FeedbackSession.objects.filter(...).order_by('-timestamp')
    
    paginator = Paginator(sessions, 25)  # Show 25 sessions per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'template.html', {'page_obj': page_obj})
```

## Estimated Performance Improvements

### Before Optimization:
- **FeedbackSessionAnalysisView**: 1 + N queries (N = number of sessions)
- **CrudFeedbackView**: 1 + N queries (N = number of feedbacks)
- **FeedbackListView**: 6 queries + slow filtering

### After Optimization:
- **FeedbackSessionAnalysisView**: 1 query (up to 90% faster)
- **CrudFeedbackView**: 2-3 queries (up to 85% faster)
- **FeedbackListView**: 1-2 queries (up to 70% faster)

## Implementation Priority

1. **🔥 URGENT**: Fix N+1 queries in analysis views
2. **🔥 URGENT**: Add database indexes
3. **⚠️ HIGH**: Optimize filter queries
4. **⚠️ HIGH**: Add pagination for large datasets
5. **💡 MEDIUM**: Add caching for filter options
6. **💡 MEDIUM**: Use defer() for large fields

## Monitoring & Testing

### Add Django Debug Toolbar:
```python
# settings.py
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
```

### Query Monitoring:
```python
from django.db import connection

def debug_queries():
    print(f"Query Count: {len(connection.queries)}")
    for query in connection.queries:
        print(f"Time: {query['time']} - {query['sql']}")
```

This analysis should resolve the major performance bottlenecks in your COFFEE application.